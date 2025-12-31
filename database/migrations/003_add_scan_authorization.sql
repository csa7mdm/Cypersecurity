-- Migration: Add Scan Authorization System
-- Date: 2025-12-31
-- Description: Implements "Permission to Scan" workflow with document verification

-- Extend authorized_targets table with verification status
ALTER TABLE authorized_targets ADD COLUMN verification_status VARCHAR(20) DEFAULT 'pending';
ALTER TABLE authorized_targets ADD COLUMN verified_by_user_id UUID REFERENCES users(id);
ALTER TABLE authorized_targets ADD COLUMN verified_at TIMESTAMP;
ALTER TABLE authorized_targets ADD COLUMN rejection_reason TEXT;

ALTER TABLE authorized_targets ADD CONSTRAINT valid_verification_status 
    CHECK (verification_status IN ('pending', 'approved', 'rejected', 'expired'));

CREATE INDEX idx_authorized_targets_status ON authorized_targets(verification_status, valid_until);

-- Scan authorization enforcement flag
ALTER TABLE scan_jobs ADD COLUMN requires_authorization BOOLEAN DEFAULT true;
ALTER TABLE scan_jobs ADD COLUMN authorization_verified BOOLEAN DEFAULT false;

-- Add constraint to prevent scans without authorization
CREATE OR REPLACE FUNCTION check_scan_authorization()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.requires_authorization AND NEW.authorization_target_id IS NULL THEN
        RAISE EXCEPTION 'Scan requires authorization but no authorization_target_id provided';
    END IF;
    
    IF NEW.requires_authorization AND NEW.authorization_target_id IS NOT NULL THEN
        -- Check if authorization is approved and valid
        PERFORM 1 FROM authorized_targets
        WHERE id = NEW.authorization_target_id
        AND verification_status = 'approved'
        AND valid_from <= NOW()
        AND valid_until >= NOW();
        
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Authorization not approved or expired';
        END IF;
        
        NEW.authorization_verified := true;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER enforce_scan_authorization
    BEFORE INSERT ON scan_jobs
    FOR EACH ROW
    EXECUTE FUNCTION check_scan_authorization();
