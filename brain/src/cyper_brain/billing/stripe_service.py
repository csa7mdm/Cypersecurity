"""
Stripe Billing Service

Implements subscription management and usage metering.
Following TDD - tests in test_stripe_billing.py
"""

import os
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, List
import stripe

logger = logging.getLogger(__name__)


class UsageLimitExceeded(Exception):
    """Raised when user exceeds their plan's scan limit"""
    pass


class PaymentFailed(Exception):
    """Raised when payment processing fails"""
    pass


@dataclass
class Plan:
    """Pricing plan definition"""
    name: str
    price_monthly: Optional[int]  # In cents, None for custom pricing
    monthly_scans: int  # -1 for unlimited
    features: List[str]
    
    # Pre-defined plans
    FREE = None
    PRO = None
    ENTERPRISE = None


# Define plan constants
Plan.FREE = Plan(
    name="free",
    price_monthly=0,
    monthly_scans=100,
    features=["100 scans/month", "Basic reports", "7-day data retention"]
)

Plan.PRO = Plan(
    name="pro",
    price_monthly=9900,  # $99/month
    monthly_scans=1000,
    features=[
        "1,000 scans/month",
        "PDF reports",
        "90-day data retention",
        "API access",
        "Priority support",
        "Advanced analytics"
    ]
)

Plan.ENTERPRISE = Plan(
    name="enterprise",
    price_monthly=None,  # Custom pricing
    monthly_scans=-1,  # Unlimited
    features=[
        "Unlimited scans",
        "Custom reports",
        "Unlimited data retention",
        "Dedicated support",
        "SLA guarantee",
        "Custom integrations",
        "On-premise deployment option"
    ]
)


@dataclass
class Subscription:
    """Represents a user subscription"""
    user_id: str
    plan: Plan
    status: str  # active, trialing, past_due, canceled
    stripe_id: Optional[str] = None
    stripe_customer_id: Optional[str] = None
    scans_used: int = 0
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    trial_end: Optional[datetime] = None
    
    @property
    def trial_days_remaining(self) -> int:
        """Calculate remaining trial days"""
        if self.trial_end and self.status == "trialing":
            delta = self.trial_end - datetime.now()
            return max(0, delta.days)
        return 0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "user_id": self.user_id,
            "plan": self.plan.name,
            "status": self.status,
            "stripe_id": self.stripe_id,
            "scans_used": self.scans_used,
            "scans_limit": self.plan.monthly_scans,
            "trial_days_remaining": self.trial_days_remaining
        }


class StripeService:
    """
    Stripe billing service
    
    Handles subscription management, usage metering, and webhooks.
    """
    
    def __init__(self, api_key: Optional[str] = None, webhook_secret: Optional[str] = None):
        """
        Initialize Stripe service
        
        Args:
            api_key: Stripe API key (or from STRIPE_API_KEY env)
            webhook_secret: Webhook signing secret (or from STRIPE_WEBHOOK_SECRET env)
        """
        self.api_key = api_key or os.getenv("STRIPE_API_KEY")
        self.webhook_secret = webhook_secret or os.getenv("STRIPE_WEBHOOK_SECRET")
        
        if self.api_key:
            stripe.api_key = self.api_key
    
    def create_subscription(
        self,
        user_id: str,
        plan: Plan,
        payment_method: str,
        customer_email: Optional[str] = None
    ) -> Subscription:
        """
        Create a new subscription
        
        Args:
            user_id: User identifier
            plan: Pricing plan
            payment_method: Stripe payment method ID
            customer_email: Customer email for Stripe customer
        
        Returns:
            Subscription object
        """
        try:
            # Create or get Stripe customer
            customer = stripe.Customer.create(
                email=customer_email,
                payment_method=payment_method,
                invoice_settings={"default_payment_method": payment_method}
            )
            
            # Create subscription
            stripe_sub = stripe.Subscription.create(
                customer=customer.id,
                items=[{"price": self._get_stripe_price_id(plan)}],
                expand=["latest_invoice.payment_intent"]
            )
            
            subscription = Subscription(
                user_id=user_id,
                plan=plan,
                status=stripe_sub.status,
                stripe_id=stripe_sub.id,
                stripe_customer_id=customer.id,
                period_start=datetime.fromtimestamp(stripe_sub.current_period_start),
                period_end=datetime.fromtimestamp(stripe_sub.current_period_end)
            )
            
            logger.info(f"Created subscription {stripe_sub.id} for user {user_id}")
            return subscription
            
        except stripe.error.CardError as e:
            logger.error(f"Card error: {e.user_message}")
            raise PaymentFailed(e.user_message)
        except Exception as e:
            logger.error(f"Subscription creation failed: {e}")
            raise
    
    def upgrade_subscription(self, subscription: Subscription, new_plan: Plan) -> Subscription:
        """
        Upgrade subscription to higher tier
        
        Args:
            subscription: Current subscription
            new_plan: New plan to upgrade to
        
        Returns:
            Updated subscription
        """
        try:
            # Modify Stripe subscription
            stripe_sub = stripe.Subscription.modify(
                subscription.stripe_id,
                items=[{
                    "id": subscription.stripe_id,
                    "price": self._get_stripe_price_id(new_plan)
                }],
                proration_behavior="always_invoice"  # Pro-rate charges
            )
            
            subscription.plan = new_plan
            subscription.status = stripe_sub.status
            
            logger.info(f"Upgraded subscription {subscription.stripe_id} to {new_plan.name}")
            return subscription
            
        except Exception as e:
            logger.error(f"Upgrade failed: {e}")
            raise
    
    def cancel_subscription(self, subscription: Subscription, immediate: bool = False):
        """
        Cancel subscription
        
        Args:
            subscription: Subscription to cancel
            immediate: If True, cancel immediately; else at period end
        """
        try:
            if immediate:
                stripe.Subscription.delete(subscription.stripe_id)
            else:
                stripe.Subscription.modify(
                    subscription.stripe_id,
                    cancel_at_period_end=True
                )
            
            logger.info(f"Canceled subscription {subscription.stripe_id}")
            
        except Exception as e:
            logger.error(f"Cancellation failed: {e}")
            raise
    
    def check_scan_quota(self, subscription: Subscription):
        """
        Check if user can perform another scan
        
        Args:
            subscription: User's subscription
        
        Raises:
            UsageLimitExceeded: If quota exceeded
        """
        # Enterprise has unlimited scans
        if subscription.plan.monthly_scans == -1:
            return
        
        if subscription.scans_used >= subscription.plan.monthly_scans:
            raise UsageLimitExceeded(
                f"You've reached your limit of {subscription.plan.monthly_scans} scans. "
                f"Please upgrade to continue scanning."
            )
    
    def increment_scan_usage(self, subscription: Subscription):
        """
        Increment scan usage counter
        
        Args:
            subscription: Subscription to update
        """
        subscription.scans_used += 1
        
        # In real implementation, update database
        # db.update_subscription(subscription)
        
        logger.info(f"User {subscription.user_id} scans: {subscription.scans_used}/{subscription.plan.monthly_scans}")
    
    def start_trial(self, user_id: str) -> Subscription:
        """
        Start 14-day trial with Pro features
        
        Args:
            user_id: User identifier
        
        Returns:
            Trial subscription
        """
        trial_end = datetime.now() + timedelta(days=14)
        
        subscription = Subscription(
            user_id=user_id,
            plan=Plan.PRO,
            status="trialing",
            trial_end=trial_end,
            period_start=datetime.now(),
            period_end=trial_end
        )
        
        logger.info(f"Started 14-day trial for user {user_id}")
        return subscription
    
    def is_trial_expired(self, subscription: Subscription) -> bool:
        """Check if trial has expired"""
        if subscription.status != "trialing" or not subscription.trial_end:
            return False
        return datetime.now() > subscription.trial_end
    
    def process_expired_trial(self, subscription: Subscription):
        """Downgrade expired trial to free plan"""
        if self.is_trial_expired(subscription):
            self.downgrade_to_free(subscription.stripe_id)
    
    def downgrade_to_free(self, stripe_subscription_id: str):
        """
        Downgrade subscription to free plan
        
        Args:
            stripe_subscription_id: Stripe subscription ID
        """
        # Cancel Stripe subscription
        try:
            stripe.Subscription.delete(stripe_subscription_id)
            logger.info(f"Downgraded subscription {stripe_subscription_id} to free")
        except Exception as e:
            logger.error(f"Downgrade failed: {e}")
    
    def handle_webhook(self, event: Dict) -> Dict:
        """
        Process Stripe webhook event
        
        Args:
            event: Webhook event data
        
        Returns:
            Processing result
        """
        event_type = event.get("type")
        
        logger.info(f"Processing webhook: {event_type}")
        
        handlers = {
            "invoice.payment_succeeded": self._handle_payment_succeeded,
            "invoice.payment_failed": self._handle_payment_failed,
            "customer.subscription.deleted": self._handle_subscription_deleted,
            "customer.subscription.updated": self._handle_subscription_updated
        }
        
        handler = handlers.get(event_type)
        if handler:
            handler(event["data"]["object"])
        
        return {"status": "processed", "event_type": event_type}
    
    def verify_webhook(self, payload: bytes, signature: str) -> Dict:
        """
        Verify webhook signature
        
        Args:
            payload: Raw request body
            signature: Stripe-Signature header
        
        Returns:
            Verified event data
        """
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, self.webhook_secret
            )
            return event
        except ValueError:
            logger.error("Invalid webhook payload")
            raise
        except stripe.error.SignatureVerificationError:
            logger.error("Invalid webhook signature")
            raise
    
    def create_invoice(self, subscription: Subscription) -> Dict:
        """
        Create invoice for subscription
        
        Args:
            subscription: Subscription to invoice
        
        Returns:
            Invoice data
        """
        invoice = stripe.Invoice.create(
            customer=subscription.stripe_customer_id,
            subscription=subscription.stripe_id
        )
        
        return {
            "id": invoice.id,
            "amount_due": invoice.amount_due,
            "status": invoice.status
        }
    
    # Private helper methods
    
    def _get_stripe_price_id(self, plan: Plan) -> str:
        """Get Stripe price ID for plan"""
        # In production, these would be actual Stripe price IDs
        price_ids = {
            "free": "",  # No Stripe price for free
            "pro": os.getenv("STRIPE_PRO_PRICE_ID", "price_pro_monthly"),
            "enterprise": os.getenv("STRIPE_ENTERPRISE_PRICE_ID", "price_enterprise")
        }
        return price_ids.get(plan.name, "")
    
    def _handle_payment_succeeded(self, invoice: Dict):
        """Handle successful payment"""
        logger.info(f"Payment succeeded for subscription {invoice.get('subscription')}")
        # Update subscription status in database
    
    def _handle_payment_failed(self, invoice: Dict):
        """Handle failed payment"""
        logger.warning(f"Payment failed for subscription {invoice.get('subscription')}")
        self.send_payment_failure_email(invoice.get('customer_email'))
    
    def _handle_subscription_deleted(self, subscription: Dict):
        """Handle subscription cancellation"""
        logger.info(f"Subscription deleted: {subscription.get('id')}")
        self.downgrade_to_free(subscription.get('id'))
    
    def _handle_subscription_updated(self, subscription: Dict):
        """Handle subscription update"""
        logger.info(f"Subscription updated: {subscription.get('id')}")
        # Sync subscription status in database
    
    def send_payment_failure_email(self, email: str):
        """Send payment failure notification"""
        # Placeholder - would integrate with email service
        logger.info(f"Sending payment failure email to {email}")
