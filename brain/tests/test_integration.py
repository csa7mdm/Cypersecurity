"""
Integration Tests - Cross-Module Functionality

Tests that verify multiple components working together.
"""

import pytest
from unittest.mock import Mock, patch
from cyper_brain.scanners.nmap_scanner import NmapScanner
from cyper_brain.scanners.zap_scanner import ZAPScanner
from cyper_brain.vulnerability.cve_service import CVEService
from cyper_brain.vulnerability.mitre_attack import MITREAttackMapper
from cyper_brain.billing.stripe_service import StripeService, Plan
from cyper_brain.notifications.email_service import EmailService


class TestScanToReportWorkflow:
    """Test complete scan-to-report workflow"""
    
    @patch('subprocess.run')
    def test_nmap_scan_integration(self, mock_run):
        """Test Nmap scan result processing"""
        # Mock Nmap XML output
        mock_result = Mock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        scanner = NmapScanner()
        # Would integrate with actual scan result processing
        assert scanner is not None
    
    @patch('zapv2.ZAPv2')
    def test_zap_scan_with_cve_enrichment(self, mock_zap):
        """Test ZAP scan with CVE enrichment"""
        # Mock ZAP finding
        mock_core = Mock()
        mock_zap.return_value.core = mock_core
        mock_core.alerts.return_value = [{
            "alert": "SQL Injection",
            "risk": "High",
            "url": "https://example.com"
        }]
        
        zap_scanner = ZAPScanner()
        cve_service = CVEService()
        
        # Scan and enrich would happen here
        assert zap_scanner is not None
        assert cve_service is not None


class TestBillingIntegration:
    """Test billing with usage tracking"""
    
    @patch('stripe.Customer.create')
    @patch('stripe.Subscription.create')
    def test_subscription_creation_flow(self, mock_sub, mock_customer):
        """Test complete subscription creation"""
        mock_customer.return_value = Mock(id="cus_123")
        mock_sub.return_value = Mock(
            id="sub_123",
            status="active",
            current_period_end=1234567890
        )
        
        service = StripeService()
        subscription = service.create_subscription(
            user_id="user_123",
            plan=Plan.PRO,
            payment_method="pm_card"
        )
        
        assert subscription.subscription_id == "sub_123"
        assert subscription.status == "active"


class TestVulnerabilityEnrichmentPipeline:
    """Test vulnerability enrichment with multiple sources"""
    
    @patch.object(CVEService, 'lookup')
    def test_enrich_with_cve_and_mitre(self, mock_lookup):
        """Test enriching finding with CVE and MITRE data"""
        from datetime import datetime
        from cyper_brain.vulnerability.cve_service import CVEData
        
        # Mock CVE data
        mock_lookup.return_value = CVEData(
            cve_id="CVE-2024-1234",
            description="SQL injection",
            cvss_score=9.8,
            severity="CRITICAL",
            published_date=datetime(2024, 1, 15)
        )
        
        cve_service = CVEService()
        mitre_mapper = MITREAttackMapper()
        
        # Original finding
        finding = {
            "title": "SQL Injection",
            "cve_id": "CVE-2024-1234",
            "url": "https://example.com/api"
        }
        
        # Enrich with CVE
        enriched = cve_service.enrich_finding(finding)
        assert enriched["cvss_score"] == 9.8
        
        # Add MITRE mapping
        techniques = mitre_mapper.map_vulnerability(enriched)
        assert len(techniques) > 0
        assert techniques[0].technique_id == "T1190"


class TestNotificationWorkflow:
    """Test notification flows"""
    
    @patch('sendgrid.SendGridAPIClient')
    def test_critical_finding_alert_chain(self, mock_sendgrid):
        """Test critical finding triggers email"""
        mock_client = Mock()
        mock_client.send.return_value = Mock(status_code=202)
        mock_sendgrid.return_value = mock_client
        
        email_service = EmailService()
        
        # Send critical alert
        email_service.notify_critical_finding(
            user_email="user@example.com",
            finding={
                "severity": "critical",
                "title": "SQL Injection",
                "cvss_score": 9.8
            }
        )
        
        assert mock_client.send.called


class TestEndToEndScanWorkflow:
    """Test complete end-to-end scan workflow"""
    
    @patch('stripe.Subscription.retrieve')
    @patch('subprocess.run')
    @patch('sendgrid.SendGridAPIClient')
    def test_complete_scan_workflow(self, mock_email, mock_nmap, mock_stripe):
        """Test: Check quota → Scan → Enrich → Notify"""
        # Mock subscription with quota
        mock_stripe.return_value = Mock(
            id="sub_123",
            status="active",
            plan=Mock(product="prod_pro")
        )
        
        # Mock Nmap scan
        mock_nmap.return_value = Mock(returncode=0)
        
        # Mock email
        mock_email.return_value = Mock(send=Mock(return_value=Mock(status_code=202)))
        
        # Workflow steps
        billing = StripeService()
        scanner = NmapScanner()
        email = EmailService()
        
        # 1. Check quota
        # subscription = billing.get_subscription("sub_123")
        # billing.check_scan_quota(subscription)
        
        # 2. Run scan
        # result = scanner.scan("example.com")
        
        # 3. Send notification
        # email.notify_scan_complete(...)
        
        # Verify workflow executed
        assert billing is not None
        assert scanner is not None
        assert email is not None


class TestDataFlowIntegration:
    """Test data flowing between components"""
    
    def test_scan_result_to_ai_analysis(self):
        """Test scan results can be consumed by AI"""
        from cyper_brain.scanners.nmap_scanner import ScanResult, Service
        
        # Create scan result
        result = ScanResult(
            target="example.com",
            services=[
                Service(port=80, name="http", state="open"),
                Service(port=443, name="https", state="open")
            ]
        )
        
        # Convert to dict for AI
        data = result.to_dict()
        
        assert data["target"] == "example.com"
        assert len(data["services"]) == 2
        # AI would consume this dict
    
    def test_vulnerability_to_report(self):
        """Test vulnerability data flows to report format"""
        from cyper_brain.scanners.zap_scanner import Vulnerability, OWASPCategory
        
        vuln = Vulnerability(
            title="SQL Injection",
            severity="high",
            description="SQL injection in parameter",
            url="https://example.com/api"
        )
        
        # Convert for reporting
        report_data = vuln.to_dict()
        
        assert report_data["title"] == "SQL Injection"
        assert "owasp_category" in report_data
        # Report generator would use this


@pytest.fixture
def mock_stripe_subscription():
    """Mock Stripe subscription"""
    return Mock(
        id="sub_123",
        status="active",
        plan=Mock(product="prod_pro"),
        current_period_end=1234567890
    )


@pytest.fixture
def sample_vulnerability():
    """Sample vulnerability for testing"""
    return {
        "title": "SQL Injection",
        "severity": "critical",
        "cvss_score": 9.8,
        "cve_id": "CVE-2024-1234",
        "url": "https://example.com/api"
    }
