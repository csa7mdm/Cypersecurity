"""
TDD Tests for SQLMap Integration

Testing automated SQL injection detection
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from cyper_brain.scanners.sqlmap_scanner import (
    SQLMapScanner,
    SQLMapResult,
    InjectionPoint,
    InjectionType
)


class TestSQLMapInitialization:
    """Test SQLMap scanner setup"""
    
    def test_scanner_initialization(self):
        """Should initialize SQLMap scanner"""
        scanner = SQLMapScanner()
        assert scanner is not None
        assert scanner.timeout > 0
    
    def test_custom_sqlmap_path(self):
        """Should support custom SQLMap path"""
        scanner = SQLMapScanner(sqlmap_path="/custom/sqlmap.py")
        assert "/custom/sqlmap.py" in scanner.sqlmap_path


class TestSQLInjectionDetection:
    """Test SQL injection vulnerability detection"""
    
    @patch('subprocess.run')
    def test_basic_sql_injection_scan(self, mock_run):
        """Should detect SQL injection in URL parameter"""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = """
        [INFO] testing 'AND boolean-based blind - WHERE or HAVING clause'
        [INFO] GET parameter 'id' appears to be 'AND boolean-based blind' injectable
        [INFO] Parameter: id (GET)
        Type: boolean-based blind
        Title: AND boolean-based blind - WHERE or HAVING clause
        Payload: id=1 AND 1=1
        """
        mock_run.return_value = mock_result
        
        scanner = SQLMapScanner()
        result = scanner.scan("https://example.com/page?id=1")
        
        assert result is not None
        assert len(result.injection_points) > 0
        assert result.injection_points[0].parameter == "id"
        assert result.injection_points[0].vulnerable is True
    
    @patch('subprocess.run')
    def test_post_parameter_injection(self, mock_run):
        """Should test POST parameters for SQL injection"""
        scanner = SQLMapScanner()
        
        result = scanner.scan(
            url="https://example.com/login",
            method="POST",
            data="username=admin&password=test"
        )
        
        # Verify SQLMap was called with POST method
        call_args = mock_run.call_args[0][0]
        assert "--method=POST" in " ".join(call_args)
        assert "--data" in " ".join(call_args)


class TestInjectionTypes:
    """Test classification of injection types"""
    
    def test_boolean_based_blind(self):
        """Should identify boolean-based blind injection"""
        injection = InjectionPoint(
            parameter="id",
            injection_type=InjectionType.BOOLEAN_BLIND,
            payload="1 AND 1=1"
        )
        
        assert injection.injection_type == InjectionType.BOOLEAN_BLIND
        assert injection.is_blind_injection()
    
    def test_time_based_blind(self):
        """Should identify time-based blind injection"""
        injection = InjectionPoint(
            parameter="id",
            injection_type=InjectionType.TIME_BLIND,
            payload="1 AND SLEEP(5)"
        )
        
        assert injection.injection_type == InjectionType.TIME_BLIND
        assert injection.is_blind_injection()
    
    def test_union_query_injection(self):
        """Should identify UNION query injection"""
        injection = InjectionPoint(
            parameter="id",
            injection_type=InjectionType.UNION_QUERY,
            payload="1 UNION SELECT NULL,NULL"
        )
        
        assert injection.injection_type == InjectionType.UNION_QUERY
        assert not injection.is_blind_injection()


class TestDatabaseFingerprinting:
    """Test database type detection"""
    
    @patch('subprocess.run')
    def test_detect_mysql_database(self, mock_run):
        """Should detect MySQL database"""
        mock_result = Mock()
        mock_result.stdout = """
        [INFO] the back-end DBMS is MySQL
        web server operating system: Linux Ubuntu
        web application technology: Apache 2.4.41
        back-end DBMS: MySQL >= 5.0
        """
        mock_run.return_value = mock_result
        
        scanner = SQLMapScanner()
        result = scanner.scan("https://example.com/page?id=1")
        
        assert result.database_type == "MySQL"
        assert "5.0" in result.database_version
    
    @patch('subprocess.run')
    def test_detect_postgresql(self, mock_run):
        """Should detect PostgreSQL database"""
        mock_result = Mock()
        mock_result.stdout = """
        [INFO] the back-end DBMS is PostgreSQL
        back-end DBMS: PostgreSQL 12.3
        """
        mock_run.return_value = mock_result
        
        scanner = SQLMapScanner()
        result = scanner.scan("https://example.com/page?id=1")
        
        assert result.database_type == "PostgreSQL"


class TestDataExtraction:
    """Test data extraction capabilities"""
    
    @patch('subprocess.run')
    def test_enumerate_databases(self, mock_run):
        """Should enumerate available databases"""
        mock_result = Mock()
        mock_result.stdout = """
        [INFO] fetching database names
        available databases [3]:
        [*] information_schema
        [*] mysql
        [*] testdb
        """
        mock_run.return_value = mock_result
        
        scanner = SQLMapScanner()
        databases = scanner.enumerate_databases("https://example.com/page?id=1")
        
        assert len(databases) == 3
        assert "testdb" in databases
    
    @patch('subprocess.run')
    def test_enumerate_tables(self, mock_run):
        """Should enumerate tables in database"""
        scanner = SQLMapScanner()
        tables = scanner.enumerate_tables(
            url="https://example.com/page?id=1",
            database="testdb"
        )
        
        # Verify correct flags were used
        call_args = mock_run.call_args[0][0]
        assert "--tables" in " ".join(call_args)
        assert "-D testdb" in " ".join(call_args)


class TestResultParsing:
    """Test SQLMap output parsing"""
    
    def test_parse_injection_results(self):
        """Should parse SQLMap output into structured data"""
        output = """
        Parameter: id (GET)
        Type: boolean-based blind
        Title: AND boolean-based blind - WHERE or HAVING clause
        Payload: id=1 AND 5678=5678
        ---
        Parameter: id (GET)
        Type: error-based
        Title: MySQL >= 5.0 error-based - Parameter replace
        Payload: id=(SELECT 1 FROM(SELECT COUNT(*))
        """
        
        scanner = SQLMapScanner()
        injections = scanner._parse_injections(output)
        
        assert len(injections) == 2
        assert injections[0].injection_type == InjectionType.BOOLEAN_BLIND
        assert injections[1].injection_type == InjectionType.ERROR_BASED
    
    def test_parse_database_info(self):
        """Should extract database information"""
        output = """
        web server operating system: Linux Ubuntu 20.04
        web application technology: PHP 7.4.3, Apache 2.4.41
        back-end DBMS: MySQL >= 5.0.12
        """
        
        scanner = SQLMapScanner()
        info = scanner._parse_database_info(output)
        
        assert info["database_type"] == "MySQL"
        assert "5.0" in info["database_version"]
        assert info["web_server"] == "Apache"


class TestScanOptions:
    """Test various scanning options"""
    
    @patch('subprocess.run')
    def test_risk_level_setting(self, mock_run):
        """Should support risk level configuration"""
        scanner = SQLMapScanner()
        scanner.scan("https://example.com?id=1", risk_level=3)
        
        call_args = mock_run.call_args[0][0]
        assert "--risk=3" in " ".join(call_args)
    
    @patch('subprocess.run')
    def test_technique_selection(self, mock_run):
        """Should support technique selection"""
        scanner = SQLMapScanner()
        scanner.scan(
            "https://example.com?id=1",
            techniques="BEUST"  # All techniques
        )
        
        call_args = mock_run.call_args[0][0]
        assert "--technique=BEUST" in " ".join(call_args)
    
    @patch('subprocess.run')
    def test_timeout_configuration(self, mock_run):
        """Should support custom timeout"""
        scanner = SQLMapScanner(timeout=300)
        scanner.scan("https://example.com?id=1")
        
        call_args = mock_run.call_args[0][0]
        assert "--timeout=300" in " ".join(call_args)


class TestErrorHandling:
    """Test error scenarios"""
    
    @patch('subprocess.run')
    def test_no_injection_found(self, mock_run):
        """Should handle case with no injection found"""
        mock_result = Mock()
        mock_result.stdout = "[WARNING] parameter 'id' does not appear to be injectable"
        mock_run.return_value = mock_result
        
        scanner = SQLMapScanner()
        result = scanner.scan("https://example.com?id=1")
        
        assert len(result.injection_points) == 0
        assert not result.is_vulnerable
    
    @patch('subprocess.run')
    def test_sqlmap_not_found(self, mock_run):
        """Should raise error if SQLMap not found"""
        mock_run.side_effect = FileNotFoundError("SQLMap not found")
        
        scanner = SQLMapScanner()
        
        with pytest.raises(FileNotFoundError):
            scanner.scan("https://example.com?id=1")


# Fixtures
@pytest.fixture
def sample_sqlmap_output():
    """Sample SQLMap output"""
    return """
    [INFO] testing 'AND boolean-based blind'
    [INFO] GET parameter 'id' appears to be injectable
    Parameter: id (GET)
    Type: boolean-based blind
    Title: AND boolean-based blind - WHERE
    Payload: id=1 AND 1=1
    
    [INFO] the back-end DBMS is MySQL
    back-end DBMS: MySQL >= 5.0
    """


@pytest.fixture
def sample_injection_point():
    """Sample injection point"""
    return InjectionPoint(
        parameter="id",
        parameter_type="GET",
        injection_type=InjectionType.BOOLEAN_BLIND,
        payload="1 AND 1=1",
        vulnerable=True,
        dbms="MySQL"
    )
