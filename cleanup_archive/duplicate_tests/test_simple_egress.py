"""
Simple test to check if LiveKit Egress Service imports work correctly.
"""

def test_imports():
    """Test that all imports work correctly."""
    try:
        from src.services.livekit_egress import (
            LiveKitEgressService,
            EgressStatus,
            OutputFormat,
            StorageProvider,
            S3Config,
            GCPConfig,
            AzureConfig
        )
        print("✅ All imports successful!")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_enum_values():
    """Test that enum values are accessible."""
    try:
        from src.services.livekit_egress import EgressStatus, OutputFormat, StorageProvider
        
        print(f"EgressStatus values: {list(EgressStatus)}")
        print(f"OutputFormat values: {list(OutputFormat)}")
        print(f"StorageProvider values: {list(StorageProvider)}")
        
        return True
    except Exception as e:
        print(f"❌ Enum test error: {e}")
        return False

def test_config_creation():
    """Test that config classes can be created."""
    try:
        from src.services.livekit_egress import S3Config, GCPConfig, AzureConfig
        
        s3_config = S3Config(
            access_key="test_key",
            secret="test_secret",
            region="us-east-1",
            bucket="test-bucket"
        )
        
        gcp_config = GCPConfig(
            credentials='{"type": "service_account"}',
            bucket="test-bucket"
        )
        
        azure_config = AzureConfig(
            account_name="testaccount",
            account_key="test_key",
            container_name="test-container"
        )
        
        print("✅ Config creation successful!")
        print(f"S3 config: {s3_config.bucket}")
        print(f"GCP config: {gcp_config.bucket}")
        print(f"Azure config: {azure_config.container_name}")
        
        return True
    except Exception as e:
        print(f"❌ Config creation error: {e}")
        return False

if __name__ == "__main__":
    print("Testing LiveKit Egress Service...")
    
    tests = [
        ("Import test", test_imports),
        ("Enum values test", test_enum_values),
        ("Config creation test", test_config_creation)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        if test_func():
            passed += 1
        else:
            print(f"Test failed: {test_name}")
    
    print(f"\n=== Results ===")
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All tests passed!")
    else:
        print("❌ Some tests failed!")