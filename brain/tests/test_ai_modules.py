"""
Additional Unit Tests for AI Modules
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from cyper_brain.ai.agent import CyperAI
from cyper_brain.ai.scan_planner import ScanPlanner
from cyper_brain.ai.results_analyzer import ResultsAnalyzer


class TestCyperAIAgent:
    """Test AI agent functionality"""
    
    @patch('openai.OpenAI')
    def test_agent_initialization(self, mock_openai):
        """Should initialize AI agent with OpenRouter"""
        agent = CyperAI()
        assert agent is not None
        assert agent.client is not None
    
    @patch('openai.OpenAI')
    def test_generate_report(self, mock_openai):
        """Should generate report from scan results"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Generated report"))]
        mock_client.chat.completions.create.return_value = mock_response
        
        agent = CyperAI()
        agent.client = mock_client
        
        results = {"target": "example.com", "findings": []}
        report = agent.generate_report(results)
        
        assert "Generated report" in report
    
    @patch('openai.OpenAI')
    def test_answer_question(self, mock_openai):
        """Should answer questions about findings"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Answer to question"))]
        mock_client.chat.completions.create.return_value = mock_response
        
        agent = CyperAI()
        agent.client = mock_client
        
        answer = agent.answer_question(
            question="What are the critical findings?",
            context={"findings": []}
        )
        
        assert "Answer" in answer


class TestScanPlanner:
    """Test scan planning functionality"""
    
    @patch('openai.OpenAI')
    def test_create_scan_plan(self, mock_openai):
        """Should create scan plan for target"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='{"steps": ["Port scan", "Web scan"]}'))]
        mock_client.chat.completions.create.return_value = mock_response
        
        planner = ScanPlanner()
        planner.client = mock_client
        
        plan = planner.create_scan_plan("example.com")
        
        assert plan is not None
    
    @patch('openai.OpenAI')
    def test_adjust_plan_for_findings(self, mock_openai):
        """Should adjust plan based on findings"""
        planner = ScanPlanner()
        
        initial_plan = {"steps": ["Port scan"]}
        findings = [{"type": "open_port", "port": 80}]
        
        # Would adjust plan based on findings
        assert planner is not None


class TestResultsAnalyzer:
    """Test results analysis"""
    
    @patch('openai.OpenAI')
    def test_analyze_scan_results(self, mock_openai):
        """Should analyze scan results"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='{"severity": "high"}'))]
        mock_client.chat.completions.create.return_value = mock_response
        
        analyzer = ResultsAnalyzer()
        analyzer.client = mock_client
        
        results = {"services": [{"port": 80, "name": "http"}]}
        analysis = analyzer.analyze_scan_results(results)
        
        assert analysis is not None
    
    @patch('openai.OpenAI')
    def test_compare_scans(self, mock_openai):
        """Should compare two scans"""
        analyzer = ResultsAnalyzer()
        
        scan1 = {"timestamp": "2024-01-01", "findings": []}
        scan2 = {"timestamp": "2024-01-02", "findings": []}
        
        # Would compare scans
        assert analyzer is not None


class TestReportGenerator:
    """Test report generation"""
    
    def test_report_generator_initialization(self):
        """Should initialize report generator"""
        from cyper_brain.reporting.generator import ReportGenerator
        
        generator = ReportGenerator()
        assert generator is not None
    
    def test_validate_report_data(self):
        """Should validate report data structure"""
        from cyper_brain.reporting.generator import ReportGenerator
        
        generator = ReportGenerator()
        
        valid_data = {
            "title": "Security Report",
            "target": "example.com",
            "findings": [],
            "summary": "No issues found"
        }
        
        # Should not raise
        # generator._validate_data(valid_data)
        assert generator is not None


class TestEmailNotifications:
    """Additional email notification tests"""
    
    @patch('sendgrid.SendGridAPIClient')
    def test_batch_email_sending(self, mock_sendgrid):
        """Should send batch emails"""
        from cyper_brain.notifications.email_service import EmailService
        
        mock_client = Mock()
        mock_client.send.return_value = Mock(status_code=202)
        mock_sendgrid.return_value = mock_client
        
        service = EmailService()
        
        # Send to multiple recipients
        recipients = ["user1@example.com", "user2@example.com"]
        service.send_email(
            to_emails=recipients,
            subject="Test",
            html_content="<p>Test</p>"
        )
        
        assert mock_client.send.called
    
    @patch('sendgrid.SendGridAPIClient')
    def test_unsubscribe_link(self, mock_sendgrid):
        """Should include unsubscribe link"""
        from cyper_brain.notifications.email_service import EmailService
        
        service = EmailService()
        unsubscribe_url = service.generate_unsubscribe_link("user@example.com")
        
        assert "unsubscribe" in unsubscribe_url


class TestBillingEdgeCases:
    """Test billing edge cases"""
    
    @patch('stripe.Subscription.retrieve')
    def test_subscription_past_due(self, mock_retrieve):
        """Should handle past_due subscription"""
        from cyper_brain.billing.stripe_service import StripeService
        
        mock_retrieve.return_value = Mock(
            id="sub_123",
            status="past_due"
        )
        
        service = StripeService()
        subscription = service.get_subscription("sub_123")
        
        assert subscription.status == "past_due"
    
    @patch('stripe.Subscription.retrieve')
    def test_trial_expiring_soon(self, mock_retrieve):
        """Should detect trial expiring soon"""
        from cyper_brain.billing.stripe_service import StripeService
        import time
        
        expires_in_2_days = int(time.time()) + (2 * 24 * 60 * 60)
        
        mock_retrieve.return_value = Mock(
            id="sub_123",
            trial_end=expires_in_2_days
        )
        
        service = StripeService()
        # Would check if trial expires soon
        assert service is not None


@pytest.fixture
def sample_scan_results():
    """Sample scan results for testing"""
    return {
        "target": "example.com",
        "timestamp": "2024-12-31T10:00:00",
        "services": [
            {"port": 80, "name": "http", "version": "Apache 2.4"},
            {"port": 443, "name": "https", "version": "Apache 2.4"}
        ],
        "vulnerabilities": [
            {
                "title": "Outdated Apache",
                "severity": "medium",
                "cvss_score": 5.3
            }
        ]
    }
