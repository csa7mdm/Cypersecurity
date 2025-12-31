"""
TDD Tests for CVSS v3.1 Calculator
"""

import pytest
from cyper_brain.vulnerability.cvss_calculator import (
    CVSSCalculator,
    CVSSVector,
    AttackVector,
    AttackComplexity,
    PrivilegesRequired,
    UserInteraction,
    Scope,
    Impact,
    CVSS_TEMPLATES
)


class TestCVSSCalculation:
    """Test CVSS score calculation"""
    
    def test_critical_sql_injection_score(self):
        """Should calculate 9.8 for SQL injection"""
        vector = CVSS_TEMPLATES["sql_injection"]
        score = CVSSCalculator.calculate_base_score(vector)
        assert score == 9.8
        assert CVSSCalculator.get_severity(score) == "CRITICAL"
    
    def test_medium_xss_score(self):
        """Should calculate correct score for reflected XSS"""
        vector = CVSS_TEMPLATES["xss_reflected"]
        score = CVSSCalculator.calculate_base_score(vector)
        assert 6.0 <= score <= 7.0
        assert CVSSCalculator.get_severity(score) == "MEDIUM"
    
    def test_vector_string_parsing(self):
        """Should parse CVSS vector string"""
        vector_string = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
        vector = CVSSCalculator.parse_vector_string(vector_string)
        
        assert vector.attack_vector == AttackVector.NETWORK
        assert vector.attack_complexity == AttackComplexity.LOW
        assert vector.privileges_required == PrivilegesRequired.NONE
    
    def test_vector_to_string(self):
        """Should convert vector to string"""
        vector = CVSSVector(
            attack_vector=AttackVector.NETWORK,
            attack_complexity=AttackComplexity.LOW,
            privileges_required=PrivilegesRequired.NONE,
            user_interaction=UserInteraction.NONE,
            scope=Scope.UNCHANGED,
            confidentiality=Impact.HIGH,
            integrity=Impact.HIGH,
            availability=Impact.HIGH
        )
        
        vector_string = vector.to_string()
        assert "CVSS:3.1" in vector_string
        assert "AV:N" in vector_string
        assert "C:H" in vector_string


class TestSeverityMapping:
    """Test severity level mapping"""
    
    def test_none_severity(self):
        """Should map 0.0 to NONE"""
        assert CVSSCalculator.get_severity(0.0) == "NONE"
    
    def test_low_severity(self):
        """Should map 0.1-3.9 to LOW"""
        assert CVSSCalculator.get_severity(0.1) == "LOW"
        assert CVSSCalculator.get_severity(3.9) == "LOW"
    
    def test_medium_severity(self):
        """Should map 4.0-6.9 to MEDIUM"""
        assert CVSSCalculator.get_severity(4.0) == "MEDIUM"
        assert CVSSCalculator.get_severity(6.9) == "MEDIUM"
    
    def test_high_severity(self):
        """Should map 7.0-8.9 to HIGH"""
        assert CVSSCalculator.get_severity(7.0) == "HIGH"
        assert CVSSCalculator.get_severity(8.9) == "HIGH"
    
    def test_critical_severity(self):
        """Should map 9.0-10.0 to CRITICAL"""
        assert CVSSCalculator.get_severity(9.0) == "CRITICAL"
        assert CVSSCalculator.get_severity(10.0) == "CRITICAL"


class TestCalculateFromString:
    """Test convenience method"""
    
    def test_calculate_from_string(self):
        """Should calculate score from vector string"""
        vector_string = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H"
        result = CVSSCalculator.calculate_from_string(vector_string)
        
        assert "score" in result
        assert "severity" in result
        assert "vector_string" in result
        assert result["score"] == 10.0
        assert result["severity"] == "CRITICAL"
