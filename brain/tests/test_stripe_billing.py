"""
TDD Tests for Stripe Billing Integration

Following TDD principles:
1. RED: Write failing tests first
2. GREEN: Implement to make tests pass
3. REFACTOR: Clean code

Testing subscription management, usage limits, and webhooks.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from cyper_brain.billing.stripe_service import (
    StripeService,
    Subscription,
    Plan,
    UsageLimitExceeded,
    PaymentFailed
)


class TestStripePlans:
    """Test pricing plan definitions"""
    
    def test_free_plan_limits(self):
        """Should define free plan with 100 scans/month limit"""
        plan = Plan.FREE
        assert plan.name == "free"
        assert plan.monthly_scans == 100
        assert plan.price_monthly == 0
        assert plan.features == ["100 scans/month", "Basic reports"]
    
    def test_pro_plan_features(self):
        """Should define Pro plan at $99/month"""
        plan = Plan.PRO
        assert plan.name == "pro"
        assert plan.price_monthly == 9900  # cents
        assert plan.monthly_scans == 1000
        assert "PDF reports" in plan.features
        assert "Priority support" in plan.features
    
    def test_enterprise_plan_unlimited(self):
        """Should define Enterprise plan with unlimited scans"""
        plan = Plan.ENTERPRISE
        assert plan.name == "enterprise"
        assert plan.monthly_scans == -1  # Unlimited
        assert plan.price_monthly is None  # Custom pricing


class TestSubscriptionManagement:
    """Test subscription lifecycle"""
    
    @patch('stripe.Subscription.create')
    def test_create_subscription(self, mock_stripe_create):
        """Should create Stripe subscription for user"""
        # Mock Stripe response
        mock_stripe_create.return_value = Mock(
            id="sub_123",
            status="active",
            current_period_end=1735689600  # Unix timestamp
        )
        
        service = StripeService(api_key="test_key")
        subscription = service.create_subscription(
            user_id="user_123",
            plan=Plan.PRO,
            payment_method="pm_test_card"
        )
        
        assert subscription.stripe_id == "sub_123"
        assert subscription.status == "active"
        assert subscription.plan == Plan.PRO
        assert subscription.user_id == "user_123"
        
        # Verify Stripe was called correctly
        mock_stripe_create.assert_called_once()
    
    @patch('stripe.Subscription.modify')
    def test_upgrade_subscription(self, mock_stripe_modify):
        """Should upgrade subscription from Free to Pro"""
        mock_stripe_modify.return_value = Mock(status="active")
        
        service = StripeService(api_key="test_key")
        subscription = Subscription(
            stripe_id="sub_123",
            user_id="user_123",
            plan=Plan.FREE,
            status="active"
        )
        
        upgraded = service.upgrade_subscription(subscription, Plan.PRO)
        
        assert upgraded.plan == Plan.PRO
        mock_stripe_modify.assert_called_once()
    
    @patch('stripe.Subscription.delete')
    def test_cancel_subscription(self, mock_stripe_delete):
        """Should cancel subscription at period end"""
        mock_stripe_delete.return_value = Mock(status="canceled")
        
        service = StripeService(api_key="test_key")
        subscription = Subscription(
            stripe_id="sub_123",
            user_id="user_123",
            plan=Plan.PRO,
            status="active"
        )
        
        service.cancel_subscription(subscription)
        
        mock_stripe_delete.assert_called_once_with("sub_123")


class TestUsageLimits:
    """Test usage metering and enforcement"""
    
    def test_enforce_usage_limit_free_plan(self):
        """Should block scans when free limit exceeded"""
        service = StripeService(api_key="test_key")
        
        # User on free plan with 100 scans used (limit is 100)
        subscription = Subscription(
            user_id="user_123",
            plan=Plan.FREE,
            scans_used=100,
            status="active"
        )
        
        with pytest.raises(UsageLimitExceeded) as exc_info:
            service.check_scan_quota(subscription)
        
        assert "100 scans" in str(exc_info.value)
        assert "upgrade" in str(exc_info.value).lower()
    
    def test_allow_scan_within_limit(self):
        """Should allow scan when under limit"""
        service = StripeService(api_key="test_key")
        
        subscription = Subscription(
            user_id="user_123",
            plan=Plan.FREE,
            scans_used=50,  # Under 100 limit
            status="active"
        )
        
        # Should not raise
        service.check_scan_quota(subscription)
    
    def test_unlimited_scans_enterprise(self):
        """Should allow unlimited scans for Enterprise"""
        service = StripeService(api_key="test_key")
        
        subscription = Subscription(
            user_id="user_123",
            plan=Plan.ENTERPRISE,
            scans_used=10000,  # Way over free limit
            status="active"
        )
        
        # Should not raise
        service.check_scan_quota(subscription)
    
    @patch('cyper_brain.billing.stripe_service.db')
    def test_increment_usage(self, mock_db):
        """Should increment scan count after scan completes"""
        service = StripeService(api_key="test_key")
        
        subscription = Subscription(
            user_id="user_123",
            plan=Plan.PRO,
            scans_used=50,
            status="active"
        )
        
        service.increment_scan_usage(subscription)
        
        assert subscription.scans_used == 51
        # Verify database update
        mock_db.update_subscription.assert_called_once()


class TestWebhookHandling:
    """Test Stripe webhook event processing"""
    
    def test_handle_payment_succeeded(self):
        """Should process successful payment webhook"""
        service = StripeService(api_key="test_key")
        
        webhook_event = {
            "type": "invoice.payment_succeeded",
            "data": {
                "object": {
                    "subscription": "sub_123",
                    "amount_paid": 9900,
                    "status": "paid"
                }
            }
        }
        
        result = service.handle_webhook(webhook_event)
        
        assert result["status"] == "processed"
        assert result["event_type"] == "invoice.payment_succeeded"
    
    def test_handle_payment_failed(self):
        """Should handle failed payment and notify user"""
        service = StripeService(api_key="test_key")
        
        webhook_event = {
            "type": "invoice.payment_failed",
            "data": {
                "object": {
                    "subscription": "sub_123",
                    "customer_email": "user@example.com"
                }
            }
        }
        
        with patch.object(service, 'send_payment_failure_email') as mock_email:
            result = service.handle_webhook(webhook_event)
            
            assert result["status"] == "processed"
            mock_email.assert_called_once()
    
    def test_handle_subscription_deleted(self):
        """Should downgrade user when subscription canceled"""
        service = StripeService(api_key="test_key")
        
        webhook_event = {
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": "sub_123",
                    "customer": "cus_123"
                }
            }
        }
        
        with patch.object(service, 'downgrade_to_free') as mock_downgrade:
            service.handle_webhook(webhook_event)
            mock_downgrade.assert_called_once_with("sub_123")
    
    def test_verify_webhook_signature(self):
        """Should verify Stripe webhook signature"""
        service = StripeService(api_key="test_key", webhook_secret="whsec_test")
        
        payload = b'{"type": "test"}'
        signature = "t=123,v1=abc123"
        
        with patch('stripe.Webhook.construct_event') as mock_verify:
            mock_verify.return_value = {"type": "test"}
            
            event = service.verify_webhook(payload, signature)
            
            assert event["type"] == "test"
            mock_verify.assert_called_once_with(
                payload, signature, "whsec_test"
            )


class TestTrialManagement:
    """Test trial period handling"""
    
    def test_create_trial_subscription(self):
        """Should create 14-day trial for new signups"""
        service = StripeService(api_key="test_key")
        
        trial_sub = service.start_trial(user_id="user_123")
        
        assert trial_sub.plan == Plan.PRO  # Trial is Pro features
        assert trial_sub.status == "trialing"
        assert trial_sub.trial_days_remaining == 14
    
    def test_trial_expiration(self):
        """Should downgrade to free when trial expires"""
        service = StripeService(api_key="test_key")
        
        expired_trial = Subscription(
            user_id="user_123",
            plan=Plan.PRO,
            status="trialing",
            trial_end=datetime.now() - timedelta(days=1)  # Expired
        )
        
        assert service.is_trial_expired(expired_trial)
        
        with patch.object(service, 'downgrade_to_free') as mock_downgrade:
            service.process_expired_trial(expired_trial)
            mock_downgrade.assert_called_once()


class TestInvoiceGeneration:
    """Test invoice creation and management"""
    
    @patch('stripe.Invoice.create')
    def test_generate_monthly_invoice(self, mock_invoice_create):
        """Should generate invoice for Pro subscription"""
        mock_invoice_create.return_value = Mock(
            id="in_123",
            amount_due=9900,
            status="open"
        )
        
        service = StripeService(api_key="test_key")
        subscription = Subscription(
            user_id="user_123",
            plan=Plan.PRO,
            stripe_id="sub_123",
            stripe_customer_id="cus_123"
        )
        
        invoice = service.create_invoice(subscription)
        
        assert invoice["id"] == "in_123"
        assert invoice["amount_due"] == 9900
        mock_invoice_create.assert_called_once()


# Fixtures
@pytest.fixture
def mock_stripe_customer():
    """Mock Stripe customer object"""
    return Mock(
        id="cus_123",
        email="user@example.com",
        subscriptions=Mock(data=[])
    )


@pytest.fixture
def sample_subscription():
    """Sample subscription for testing"""
    return Subscription(
        stripe_id="sub_123",
        user_id="user_123",
        plan=Plan.PRO,
        status="active",
        scans_used=0,
        period_start=datetime.now(),
        period_end=datetime.now() + timedelta(days=30)
    )
