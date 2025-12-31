package api

import (
	"context"
	"net/http"
	"time"

	"github.com/cyper-security/gateway/internal/audit"
	"github.com/gin-gonic/gin"
	"github.com/jmoiron/sqlx"
	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"
)

const EmergencyStopKey = "emergency:stop:active"

type EmergencyHandler struct {
	db          *sqlx.DB
	redis       *redis.Client
	logger      *zap.Logger
	auditLogger *audit.AuditLogger
}

func NewEmergencyHandler(db *sqlx.DB, redisClient *redis.Client, auditLogger *audit.AuditLogger, logger *zap.Logger) *EmergencyHandler {
	return &EmergencyHandler{
		db:          db,
		redis:       redisClient,
		logger:      logger,
		auditLogger: auditLogger,
	}
}

// ActivateEmergencyStop handles POST /api/v1/emergency/stop
func (h *EmergencyHandler) ActivateEmergencyStop(c *gin.Context) {
	userID := c.GetString("user_id")

	var req struct {
		Reason   string `json:"reason" binding:"required"`
		Duration int    `json:"duration_minutes"` // Optional, defaults to 60 minutes
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if req.Duration == 0 {
		req.Duration = 60 // Default: 1 hour
	}

	ctx := context.Background()

	// Set emergency stop flag in Redis with expiration
	err := h.redis.Set(ctx, EmergencyStopKey, req.Reason, time.Duration(req.Duration)*time.Minute).Err()
	if err != nil {
		h.logger.Error("Failed to set emergency stop", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to activate emergency stop"})
		return
	}

	// Stop all running scans
	result, err := h.db.Exec(`
		UPDATE scan_jobs
		SET status = 'stopped', 
		    error_message = 'Emergency stop activated: ' || $1,
		    completed_at = NOW()
		WHERE status IN ('pending', 'running')
	`, req.Reason)

	if err != nil {
		h.logger.Error("Failed to stop scans", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to stop scans"})
		return
	}

	rowsAffected, _ := result.RowsAffected()

	// Audit log
	h.auditLogger.LogSecurityEvent(ctx, userID, "emergency_stop_activated", "", "critical", map[string]interface{}{
		"reason":           req.Reason,
		"duration_minutes": req.Duration,
		"scans_stopped":    rowsAffected,
	})

	h.logger.Warn("Emergency stop activated",
		zap.String("user_id", userID),
		zap.String("reason", req.Reason),
		zap.Int64("scans_stopped", rowsAffected),
	)

	c.JSON(http.StatusOK, gin.H{
		"message":          "Emergency stop activated",
		"scans_stopped":    rowsAffected,
		"duration_minutes": req.Duration,
		"expires_at":       time.Now().Add(time.Duration(req.Duration) * time.Minute),
	})
}

// DeactivateEmergencyStop handles POST /api/v1/emergency/resume
func (h *EmergencyHandler) DeactivateEmergencyStop(c *gin.Context) {
	userID := c.GetString("user_id")
	ctx := context.Background()

	// Remove emergency stop flag
	err := h.redis.Del(ctx, EmergencyStopKey).Err()
	if err != nil {
		h.logger.Error("Failed to deactivate emergency stop", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to deactivate emergency stop"})
		return
	}

	// Audit log
	h.auditLogger.LogSecurityEvent(ctx, userID, "emergency_stop_deactivated", "", "high", map[string]interface{}{
		"resumed_by": userID,
	})

	h.logger.Info("Emergency stop deactivated", zap.String("user_id", userID))

	c.JSON(http.StatusOK, gin.H{
		"message": "Emergency stop deactivated - scan operations resumed",
	})
}

// GetEmergencyStatus handles GET /api/v1/emergency/status
func (h *EmergencyHandler) GetEmergencyStatus(c *gin.Context) {
	ctx := context.Background()

	// Check if emergency stop is active
	reason, err := h.redis.Get(ctx, EmergencyStopKey).Result()
	if err == redis.Nil {
		c.JSON(http.StatusOK, gin.H{
			"active": false,
		})
		return
	}

	if err != nil {
		h.logger.Error("Failed to get emergency status", zap.Error(err))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to get status"})
		return
	}

	// Get TTL
	ttl, err := h.redis.TTL(ctx, EmergencyStopKey).Result()
	if err != nil {
		h.logger.Error("Failed to get TTL", zap.Error(err))
	}

	c.JSON(http.StatusOK, gin.H{
		"active":     true,
		"reason":     reason,
		"expires_in": ttl.Seconds(),
		"expires_at": time.Now().Add(ttl),
	})
}

// CheckEmergencyStop is a middleware that blocks requests if emergency stop is active
func (h *EmergencyHandler) CheckEmergencyStop() gin.HandlerFunc {
	return func(c *gin.Context) {
		ctx := context.Background()

		// Check if emergency stop is active
		_, err := h.redis.Get(ctx, EmergencyStopKey).Result()
		if err == redis.Nil {
			// Not active, proceed
			c.Next()
			return
		}

		if err != nil {
			h.logger.Error("Failed to check emergency stop", zap.Error(err))
			c.Next() // Allow on error (fail open for availability)
			return
		}

		// Emergency stop is active - block scan creation
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"error":   "Emergency stop is active",
			"message": "All scan operations are temporarily suspended",
		})
		c.Abort()
	}
}
