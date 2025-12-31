package api

import (
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"fmt"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/jmoiron/sqlx"
	"go.uber.org/zap"
)

type ScanAuthorizationHandler struct {
	db     *sqlx.DB
	logger *zap.Logger
}

func NewScanAuthorizationHandler(db *sqlx.DB, logger *zap.Logger) *ScanAuthorizationHandler {
	return &ScanAuthorizationHandler{
		db:     db,
		logger: logger,
	}
}

type SubmitAuthorizationRequest struct {
	TargetType          string    `json:"target_type" binding:"required"` // ip, domain, cidr, etc.
	TargetValue         string    `json:"target_value" binding:"required"`
	AuthorizedBy        string    `json:"authorized_by" binding:"required"`
	AuthorizationDocURL string    `json:"authorization_document_url" binding:"required"`
	ValidFrom           time.Time `json:"valid_from" binding:"required"`
	ValidUntil          time.Time `json:"valid_until" binding:"required"`
	ScopeLimitations    string    `json:"scope_limitations"` // JSON string
}

type Authorization struct {
	ID                       string     `json:"id" db:"id"`
	OrganizationID           string     `json:"organization_id" db:"organization_id"`
	TargetType               string     `json:"target_type" db:"target_type"`
	TargetValue              string     `json:"target_value" db:"target_value"`
	AuthorizationDocumentURL string     `json:"authorization_document_url" db:"authorization_document_url"`
	AuthorizationHash        string     `json:"authorization_hash" db:"authorization_hash"`
	AuthorizedBy             string     `json:"authorized_by" db:"authorized_by"`
	ValidFrom                time.Time  `json:"valid_from" db:"valid_from"`
	ValidUntil               time.Time  `json:"valid_until" db:"valid_until"`
	VerificationStatus       string     `json:"verification_status" db:"verification_status"`
	VerifiedByUserID         *string    `json:"verified_by_user_id" db:"verified_by_user_id"`
	VerifiedAt               *time.Time `json:"verified_at" db:"verified_at"`
	RejectionReason          *string    `json:"rejection_reason" db:"rejection_reason"`
	CreatedAt                time.Time  `json:"created_at" db:"created_at"`
}

// SubmitAuthorization handles POST /api/v1/scan-authorizations
func (h *ScanAuthorizationHandler) SubmitAuthorization(c *gin.Context) {
	orgID := c.GetString("organization_id")
	if orgID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Organization context required"})
		return
	}

	var req SubmitAuthorizationRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Validate time range
	if req.ValidUntil.Before(req.ValidFrom) {
		c.JSON(http.StatusBadRequest, gin.H{"error": "valid_until must be after valid_from"})
		return
	}

	// Compute hash of authorization document URL (as proof it was submitted)
	hash := sha256.Sum256([]byte(req.AuthorizationDocURL))
	authHash := hex.EncodeToString(hash[:])

	authID := uuid.New()

	// Insert authorization
	_, err := h.db.Exec(`
		INSERT INTO authorized_targets (
			id, organization_id, target_type, target_value,
			authorization_document_url, authorization_hash,
			authorized_by, valid_from, valid_until, verification_status
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'pending')
	`, authID, orgID, req.TargetType, req.TargetValue,
		req.AuthorizationDocURL, authHash,
		req.AuthorizedBy, req.ValidFrom, req.ValidUntil)

	if err != nil {
		h.logger.Error("Failed to submit authorization", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to submit authorization"})
		return
	}

	c.JSON(http.StatusCreated, gin.H{
		"id":                  authID.String(),
		"verification_status": "pending",
		"message":             "Authorization submitted for review",
	})
}

// ListAuthorizations handles GET /api/v1/scan-authorizations
func (h *ScanAuthorizationHandler) ListAuthorizations(c *gin.Context) {
	orgID := c.GetString("organization_id")
	if orgID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Organization context required"})
		return
	}

	status := c.Query("status") // Filter by status

	query := `
		SELECT * FROM authorized_targets
		WHERE organization_id = $1
	`
	args := []interface{}{orgID}

	if status != "" {
		query += ` AND verification_status = $2`
		args = append(args, status)
	}

	query += ` ORDER BY created_at DESC`

	var authorizations []Authorization
	err := h.db.Select(&authorizations, query, args...)
	if err != nil {
		h.logger.Error("Failed to list authorizations", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to list authorizations"})
		return
	}

	c.JSON(http.StatusOK, authorizations)
}

// VerifyAuthorization handles POST /api/v1/scan-authorizations/:id/verify
func (h *ScanAuthorizationHandler) VerifyAuthorization(c *gin.Context) {
	authID := c.Param("id")
	userID := c.GetString("user_id")

	var req struct {
		Action string `json:"action" binding:"required"` // approve or reject
		Reason string `json:"reason"`                    // Only for reject
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if req.Action != "approve" && req.Action != "reject" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "action must be 'approve' or 'reject'"})
		return
	}

	// Check if authorization exists
	var auth Authorization
	err := h.db.Get(&auth, "SELECT * FROM authorized_targets WHERE id = $1", authID)
	if err == sql.ErrNoRows {
		c.JSON(http.StatusNotFound, gin.H{"error": "Authorization not found"})
		return
	}

	if err != nil {
		h.logger.Error("Failed to fetch authorization", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to fetch authorization"})
		return
	}

	// Update verification status
	newStatus := "approved"
	if req.Action == "reject" {
		newStatus = "rejected"
	}

	var updateQuery string
	var args []interface{}

	if newStatus == "rejected" {
		updateQuery = `
			UPDATE authorized_targets
			SET verification_status = $1, verified_by_user_id = $2, verified_at = NOW(), rejection_reason = $3
			WHERE id = $4
		`
		args = []interface{}{newStatus, userID, req.Reason, authID}
	} else {
		updateQuery = `
			UPDATE authorized_targets
			SET verification_status = $1, verified_by_user_id = $2, verified_at = NOW()
			WHERE id = $3
		`
		args = []interface{}{newStatus, userID, authID}
	}

	_, err = h.db.Exec(updateQuery, args...)
	if err != nil {
		h.logger.Error("Failed to update authorization", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to update authorization"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"id":                  authID,
		"verification_status": newStatus,
		"message":             fmt.Sprintf("Authorization %s", req.Action+"d"),
	})
}

// CheckTargetAuthorization handles POST /api/v1/scan-authorizations/check
// This is used before creating a scan to verify target is authorized
func (h *ScanAuthorizationHandler) CheckTargetAuthorization(c *gin.Context) {
	orgID := c.GetString("organization_id")
	if orgID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Organization context required"})
		return
	}

	var req struct {
		TargetType  string `json:"target_type" binding:"required"`
		TargetValue string `json:"target_value" binding:"required"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Check if there's a valid, approved authorization
	var authID string
	err := h.db.Get(&authID, `
		SELECT id FROM authorized_targets
		WHERE organization_id = $1
		AND target_type = $2
		AND target_value = $3
		AND verification_status = 'approved'
		AND valid_from <= NOW()
		AND valid_until >= NOW()
		LIMIT 1
	`, orgID, req.TargetType, req.TargetValue)

	if err == sql.ErrNoRows {
		c.JSON(http.StatusOK, gin.H{
			"authorized":       false,
			"authorization_id": nil,
			"message":          "No valid authorization found for this target",
		})
		return
	}

	if err != nil {
		h.logger.Error("Failed to check authorization", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to check authorization"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"authorized":       true,
		"authorization_id": authID,
	})
}
