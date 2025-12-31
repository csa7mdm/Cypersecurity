package main

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/cyper-security/gateway/internal/api"
	"github.com/cyper-security/gateway/internal/audit"
	"github.com/cyper-security/gateway/internal/auth"
	"github.com/cyper-security/gateway/internal/brain"
	"github.com/cyper-security/gateway/internal/rbac"
	"github.com/gin-gonic/gin"
	"github.com/jmoiron/sqlx"
	"github.com/joho/godotenv"
	_ "github.com/lib/pq"
	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"
)

func main() {
	// Load environment variables
	_ = godotenv.Load()

	// Initialize logger
	logger, _ := zap.NewProduction()
	defer logger.Sync()

	logger.Info("Starting Cyper Gateway...")

	// Database connection
	dbHost := getEnv("DB_HOST", "localhost")
	dbPort := getEnv("DB_PORT", "5432")
	dbName := getEnv("DB_NAME", "cyper_security")
	dbUser := getEnv("DB_USER", "postgres")
	dbPassword := getEnv("DB_PASSWORD", "postgres")

	dsn := fmt.Sprintf("host=%s port=%s dbname=%s user=%s password=%s sslmode=disable",
		dbHost, dbPort, dbName, dbUser, dbPassword)

	db, err := sqlx.Connect("postgres", dsn)
	if err != nil {
		logger.Fatal("Failed to connect to database", zap.Error(err))
	}
	defer db.Close()

	logger.Info("Connected to PostgreSQL")

	// Redis connection
	redisURL := getEnv("REDIS_URL", "localhost:6379")
	redisClient := redis.NewClient(&redis.Options{
		Addr:     redisURL,
		Password: os.Getenv("REDIS_PASSWORD"),
		DB:       0,
	})

	ctx := context.Background()
	if err := redisClient.Ping(ctx).Err(); err != nil {
		logger.Warn("Failed to connect to Redis", zap.Error(err))
	} else {
		logger.Info("Connected to Redis")
	}
	defer redisClient.Close()

	// Initialize services
	jwtSecret := os.Getenv("JWT_SECRET")
	if jwtSecret == "" {
		jwtSecret = "default-secret-change-in-production"
		logger.Warn("Using default JWT_SECRET - CHANGE THIS IN PRODUCTION")
	}

	centralAuthURL := os.Getenv("CENTRAL_AUTH_SERVER_URL")
	brainURL := getEnv("BRAIN_URL", "http://brain:50051")
	pulseInterval := 5 * time.Minute

	brainClient := brain.NewClient(brainURL, logger)
	authService := auth.NewAuthService(db, redisClient, jwtSecret, centralAuthURL, pulseInterval, logger)
	auditLogger := audit.NewAuditLogger(db, logger)

	// Start authorization pulse checker
	go authService.StartPulseCheck(ctx)

	// Set Gin mode
	if os.Getenv("GIN_MODE") == "release" {
		gin.SetMode(gin.ReleaseMode)
	}

	// Create router
	router := gin.Default()

	// Health check
	router.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"status":    "healthy",
			"timestamp": time.Now().UTC(),
			"version":   "0.1.0",
		})
	})

	// API v1 routes
	v1 := router.Group("/v1")
	{
		authHandler := api.NewAuthHandler(authService, auditLogger)
		reportHandler := api.NewReportHandler(brainClient, logger)
		orgHandler := api.NewOrganizationHandler(db, logger)
		scanAuthHandler := api.NewScanAuthorizationHandler(db, logger)
		emergencyHandler := api.NewEmergencyHandler(db, redisClient, auditLogger, logger)

		// Public routes
		auth := v1.Group("/auth")
		{
			auth.POST("/register", authHandler.Register)
			auth.POST("/login", authHandler.Login)
			auth.POST("/accept-terms", authHandler.AcceptTerms)
		}

		// Protected routes
		protected := v1.Group("")
		protected.Use(authService.AuthMiddleware())
		{
			protected.POST("/auth/logout", authHandler.Logout)
			protected.GET("/auth/pulse", authHandler.AuthPulse)

			// Organization management
			protected.POST("/organizations", orgHandler.CreateOrganization)
			protected.GET("/organizations", orgHandler.ListOrganizations)
			protected.GET("/organizations/:id", orgHandler.GetOrganization)

			// Organization invites (requires permission)
			protected.POST("/organizations/:id/invite",
				rbac.RequirePermission(rbac.PermInviteUsers, logger),
				orgHandler.InviteUser,
			)

			// Scan routes (require permissions)
			protected.POST("/scans",
				rbac.RequirePermission(rbac.PermCreateScan, logger),
				// TODO: scan handler
			)

			// Report generation (requires permission)
			protected.POST("/scans/:id/report",
				rbac.RequirePermission(rbac.PermGenerateReport, logger),
				reportHandler.GenerateReport,
			)

			// TODO: Add monitoring routes
		}
	}

	// Get port
	port := os.Getenv("API_PORT")
	if port == "" {
		port = "8080"
	}

	// Create HTTP server
	srv := &http.Server{
		Addr:    fmt.Sprintf(":%s", port),
		Handler: router,
	}

	// Start server in goroutine
	go func() {
		logger.Info("Cyper Gateway started", zap.String("port", port))
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.Fatal("Failed to start server", zap.Error(err))
		}
	}()

	// Wait for interrupt signal
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	logger.Info("Shutting down server...")

	// Graceful shutdown
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := srv.Shutdown(shutdownCtx); err != nil {
		logger.Fatal("Server forced to shutdown", zap.Error(err))
	}

	logger.Info("Server exited")
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}
