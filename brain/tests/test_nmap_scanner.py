"""
TDD Tests for Nmap Scanner Integration

Following TDD principles:
1. RED: Write failing test
2. GREEN: Implement minimum code to pass
3. REFACTOR: Improve code quality
"""

import pytest
from unittest.mock import Mock, patch
from cyper_brain.scanners.nmap_scanner import NmapScanner, ScanResult, Service


class TestNmapScannerBasic:
    """Test basic Nmap scanning functionality"""
    
    def test_nmap_scanner_initialization(self):
        """Should initialize scanner with default settings"""
        scanner = NmapScanner()
        assert scanner is not None
        assert scanner.timeout == 300  # Default 5 minutes
    
    def test_scan_basic_ports(self):
        """Should scan common ports and return results"""
        scanner = NmapScanner()
        
        # Using scanme.nmap.org (official test server)
        results = scanner.scan(
            target="scanme.nmap.org",
            ports="22,80,443"
        )
        
        assert results is not None
        assert isinstance(results, ScanResult)
        assert results.target == "scanme.nmap.org"
        assert len(results.open_ports) > 0
    
    def test_scan_detects_open_port(self):
        """Should correctly identify open ports"""
        scanner = NmapScanner()
        results = scanner.scan("scanme.nmap.org", ports="22,80,443")
        
        # scanme.nmap.org typically has port 80 open
        assert results.is_port_open(80) or results.is_port_open(443)
    
    def test_scan_detects_service_names(self):
        """Should detect service names on open ports"""
        scanner = NmapScanner()
        results = scanner.scan("scanme.nmap.org", ports="22,80", service_detection=True)
        
        # Should detect HTTP or SSH services
        services = results.get_services()
        assert len(services) > 0
        assert any(s.name in ["http", "ssh", "https"] for s in services)


class TestNmapVersionDetection:
    """Test service version detection"""
    
    def test_version_detection_enabled(self):
        """Should detect service versions when enabled"""
        scanner = NmapScanner()
        results = scanner.scan(
            "scanme.nmap.org",
            ports="80",
            version_detection=True
        )
        
        services = results.get_services()
        if services:
            service = services[0]
            # Version might not always be detected, but the attempt should be made
            assert hasattr(service, 'version')
    
    def test_os_detection(self):
        """Should attempt OS detection when enabled"""
        scanner = NmapScanner()
        results = scanner.scan(
            "scanme.nmap.org",
            ports="22,80",
            os_detection=True
        )
        
        # OS detection may not always succeed (requires root)
        assert hasattr(results, 'os_matches')


class TestNmapAsyncExecution:
    """Test async scanning capabilities"""
    
    @pytest.mark.asyncio
    async def test_async_scan(self):
        """Should support async scanning"""
        scanner = NmapScanner()
        results = await scanner.scan_async(
            "scanme.nmap.org",
            ports="80"
        )
        
        assert results is not None
        assert isinstance(results, ScanResult)
    
    @pytest.mark.asyncio
    async def test_concurrent_scans(self):
        """Should handle multiple concurrent scans"""
        scanner = NmapScanner()
        
        targets = ["scanme.nmap.org", "example.com"]
        tasks = [
            scanner.scan_async(target, ports="80")
            for target in targets
        ]
        
        results = await asyncio.gather(*tasks)
        assert len(results) == 2
        assert all(isinstance(r, ScanResult) for r in results)


class TestNmapResultParser:
    """Test XML result parsing"""
    
    def test_parse_xml_output(self):
        """Should parse Nmap XML output correctly"""
        sample_xml = """<?xml version="1.0"?>
        <nmaprun>
            <host>
                <address addr="45.33.32.156" addrtype="ipv4"/>
                <ports>
                    <port protocol="tcp" portid="22">
                        <state state="open"/>
                        <service name="ssh" product="OpenSSH" version="6.6.1p1"/>
                    </port>
                    <port protocol="tcp" portid="80">
                        <state state="open"/>
                        <service name="http" product="Apache" version="2.4.7"/>
                    </port>
                </ports>
            </host>
        </nmaprun>
        """
        
        parser = NmapResultParser()
        results = parser.parse_xml(sample_xml)
        
        assert results.target == "45.33.32.156"
        assert len(results.open_ports) == 2
        assert 22 in results.open_ports
        assert 80 in results.open_ports
        
        ssh_service = results.get_service(22)
        assert ssh_service.name == "ssh"
        assert ssh_service.product == "OpenSSH"
        assert ssh_service.version == "6.6.1p1"


class TestNmapErrorHandling:
    """Test error handling and edge cases"""
    
    def test_invalid_target(self):
        """Should raise exception for invalid target"""
        scanner = NmapScanner()
        
        with pytest.raises(ValueError, match="Invalid target"):
            scanner.scan("invalid..target..com")
    
    def test_scan_timeout(self):
        """Should handle scan timeouts gracefully"""
        scanner = NmapScanner(timeout=1)  # 1 second timeout
        
        with pytest.raises(TimeoutError):
            scanner.scan("10.0.0.1", ports="1-65535")  # Full port scan will timeout
    
    def test_no_open_ports(self):
        """Should handle scans with no open ports"""
        scanner = NmapScanner()
        results = scanner.scan("example.com", ports="1-10")  # Unlikely to have low ports open
        
        assert isinstance(results, ScanResult)
        # Even with no open ports, should return valid result
        assert results.open_ports is not None


class TestNmapIntegrationWithBrain:
    """Test integration with Brain AI service"""
    
    def test_scan_result_to_analysis(self):
        """Should convert scan results to AI analysis format"""
        scanner = NmapScanner()
        results = scanner.scan("scanme.nmap.org", ports="22,80")
        
        # Convert to dict for AI processing
        analysis_data = results.to_dict()
        
        assert "target" in analysis_data
        assert "open_ports" in analysis_data
        assert "services" in analysis_data
        assert isinstance(analysis_data["services"], list)


# Fixtures for mocking
@pytest.fixture
def mock_nmap_output():
    """Mock Nmap XML output for testing"""
    return """<?xml version="1.0"?>
    <nmaprun>
        <host>
            <address addr="192.168.1.1" addrtype="ipv4"/>
            <ports>
                <port protocol="tcp" portid="80">
                    <state state="open"/>
                    <service name="http"/>
                </port>
            </ports>
        </host>
    </nmaprun>
    """


@pytest.fixture
def mock_scan_result():
    """Mock ScanResult for testing"""
    return ScanResult(
        target="192.168.1.1",
        open_ports=[80, 443],
        services=[
            Service(port=80, name="http", product="Apache", version="2.4.41"),
            Service(port=443, name="https", product="Apache", version="2.4.41"),
        ]
    )
