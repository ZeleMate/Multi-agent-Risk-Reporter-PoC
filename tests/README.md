# Test Suite Documentation

This directory contains comprehensive tests for the multi-agent risk reporter system.

## Test Structure

### `conftest.py`
Shared pytest fixtures and configuration for all tests:
- `mock_config`: Mocked application configuration
- `sample_email_data`: Sample email data for testing
- `sample_thread_data`: Sample email thread data
- `sample_chunks`: Sample text chunks with metadata
- `mock_openai_response`: Mock OpenAI API response
- Various mock objects for ChromaDB, HuggingFace models, etc.

### Test Files

#### `test_config.py`
Unit tests for configuration management:
- `TestConfigManager`: Tests for YAML loading and validation
- `TestAppConfig`: Tests for application configuration
- `TestConfigDataclasses`: Tests for individual config classes
- `TestConfigValidation`: Tests for configuration validation

#### `test_ingestion.py`
Unit tests for data ingestion and parsing:
- `TestNormalizeDate`: Date normalization tests
- `TestParseColleagues`: Colleagues file parsing tests
- `TestParseRecipients`: Email recipients parsing tests
- `TestRemoveQuotedReplies`: Quote removal tests
- `TestParseSingleEmail`: Single email parsing tests
- `TestProcessEmailData`: Full data processing pipeline tests

#### `test_retrieval.py`
Unit tests for vector store and retrieval:
- `TestVectorStore`: VectorStore functionality tests
- `TestHybridRetriever`: HybridRetriever functionality tests

#### `test_agents.py`
Unit tests for AI agents with mocked LLM calls:
- `TestAnalyzerAgent`: Analyzer agent tests
- `TestVerifierAgent`: Verifier agent tests
- `TestComposerAgent`: Composer agent tests
- `TestGraph`: LangGraph pipeline tests

#### `test_integration.py`
Integration tests for the complete pipeline:
- `TestDataIngestionPipeline`: Full data ingestion workflow
- `TestVectorStorePipeline`: Vector store pipeline
- `TestRetrievalPipeline`: Retrieval pipeline
- `TestFullPipeline`: Complete multi-agent pipeline
- `TestErrorHandling`: Error handling tests

## Running Tests

### Basic Test Execution
```bash
# Run all tests
make test

# Run with pytest directly
pytest tests/

# Run specific test file
pytest tests/test_config.py

# Run specific test class
pytest tests/test_config.py::TestConfigManager

# Run specific test function
pytest tests/test_config.py::TestConfigManager::test_load_from_yaml_valid_file
```

### Test Configuration
The test suite uses `pytest.ini` for configuration:
- Verbose output (`-v`)
- Short traceback format (`--tb=short`)
- Strict marker checking
- Custom markers for test categorization
- Environment variable setup

### Test Categories (Markers)
```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run tests for specific component
pytest -m config
pytest -m ingestion
pytest -m retrieval
pytest -m agents
pytest -m pipeline
```

### Coverage Reporting
```bash
# Run with coverage (requires coverage package)
tox -e coverage

# Generate HTML coverage report
open htmlcov/index.html
```

## Test Design Principles

### 1. **Mock-Based Testing**
All external dependencies (LLM APIs, ChromaDB, file systems) are mocked to ensure:
- Fast test execution
- No external dependencies
- Deterministic test results
- Isolation of tested components

### 2. **Comprehensive Coverage**
Tests cover:
- **Happy path scenarios**: Normal operation
- **Edge cases**: Empty inputs, invalid data, boundary conditions
- **Error handling**: Exception scenarios, graceful degradation
- **Configuration variations**: Different config settings

### 3. **Professional Test Structure**
- **Descriptive test names**: Clear indication of what is being tested
- **Arrange-Act-Assert pattern**: Clear test structure
- **Parameterized tests**: Multiple inputs for same test logic
- **Fixture reuse**: Shared test data and setup

### 4. **Integration Testing**
- **Pipeline testing**: End-to-end workflow testing
- **Component interaction**: Testing how components work together
- **Error propagation**: Testing error handling across components

## Test Data

### Sample Data
The tests use realistic sample data including:
- Email threads with various formats
- Colleagues information with roles
- Text chunks with metadata
- Mock LLM responses in YAML format

### Fixtures
All test data is provided through pytest fixtures in `conftest.py`:
- Easy to modify and extend
- Reusable across multiple test files
- Consistent data across tests

## CI/CD Integration

The test suite is integrated with the CI pipeline:
- Runs on every push/PR
- Uses tox for multi-environment testing
- Generates coverage reports
- Fails on test failures or coverage drops

## Adding New Tests

### 1. **Identify Test Type**
- **Unit test**: Single function/class testing
- **Integration test**: Multiple components interaction
- **Regression test**: Bug fix verification

### 2. **Choose Test File**
- `test_config.py`: Configuration-related tests
- `test_ingestion.py`: Data processing tests
- `test_retrieval.py`: Vector store/retrieval tests
- `test_agents.py`: AI agent tests
- `test_integration.py`: Multi-component tests

### 3. **Follow Naming Conventions**
```python
def test_function_name_descriptive():
    """Test docstring describing what is tested."""
    # Arrange
    # Act
    # Assert
```

### 4. **Use Appropriate Fixtures**
```python
def test_example(mock_config, sample_chunks):
    # Use fixtures for consistent test data
```

### 5. **Add Markers**
```python
@pytest.mark.unit
@pytest.mark.config
def test_configuration_loading():
    # Test with appropriate markers
```

## Best Practices

### **Test Isolation**
- Each test should be independent
- Use fixtures for setup/cleanup
- Avoid test interdependencies

### **Mock Usage**
- Mock external services (APIs, databases)
- Mock file system operations
- Mock time-dependent functions

### **Assertion Quality**
- Test specific behaviors, not implementation details
- Use descriptive assertion messages
- Test both positive and negative cases

### **Performance**
- Keep tests fast (< 1 second per test)
- Use appropriate mocking to avoid slow operations
- Parallel execution support

### **Maintenance**
- Update tests when functionality changes
- Remove obsolete tests
- Keep test data current with schema changes

## Troubleshooting

### **Common Issues**
1. **Import errors**: Check PYTHONPATH and virtual environment
2. **Mock failures**: Verify mock setup and assertions
3. **Fixture errors**: Check fixture dependencies and scope
4. **Coverage issues**: Ensure test files are in correct location

### **Debugging Tests**
```bash
# Run with debug output
pytest -v -s --pdb

# Run specific failing test
pytest tests/test_file.py::TestClass::test_method -v

# Check coverage for specific file
coverage run -m pytest tests/test_file.py
coverage report -m
```

This test suite provides comprehensive coverage of the multi-agent risk reporter system while maintaining professional standards and best practices.
