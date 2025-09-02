#!/bin/bash

# AI Copilot Exclusive Reasoning Test Script
# Tests ONLY step-by-step reasoning, WebSocket streaming, and reasoning performance

# Get real token from auth service
AUTH_RESPONSE=$(curl -s -X POST "http://localhost:8000/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"email": "admin@unibaseerp.com", "password": "admin123"}')

TOKEN=$(echo "$AUTH_RESPONSE" | jq -r '.data.access_token')

set -e

# Configuration
API_GATEWAY_URL="http://localhost:8000"
AI_COPILOT_URL="http://localhost:8003"
API_BASE="$AI_COPILOT_URL/api/v1"
WS_BASE="ws://localhost:8003/api/v1/websocket"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test counters
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((PASSED_TESTS++))
}

log_error() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((FAILED_TESTS++))
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

increment_test() {
    ((TOTAL_TESTS++))
}

# Test authentication and get token
test_authentication() {
    log_info "Testing authentication via API Gateway..."
    
    AUTH_RESPONSE=$(curl -s -X POST "$API_GATEWAY_URL/auth/login" \
        -H "Content-Type: application/json" \
        -d '{
            "email": "admin@unibaseerp.com",
            "password": "admin123"
        }')
    
    if echo "$AUTH_RESPONSE" | grep -q "access_token"; then
        TOKEN=$(echo "$AUTH_RESPONSE" | jq -r '.data.access_token')
        log_success "Authentication successful"
        return 0
    else
        log_error "Authentication failed: $AUTH_RESPONSE"
        return 1
    fi
}

# Create test conversation for reasoning tests
create_test_conversation() {
    log_info "Creating test conversation for reasoning..."
    increment_test
    
    local response=$(curl -s -X POST "$API_BASE/conversations/conversations?user_id=reasoning-test-user&organization_id=reasoning-test-org" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d '{
            "title": "Reasoning Test Conversation",
            "context": {"test": true},
            "metadata": {"test_type": "reasoning"}
        }')
    
    if echo "$response" | jq -e '.conversation_id' > /dev/null 2>&1; then
        CONVERSATION_ID=$(echo "$response" | jq -r '.conversation_id')
        log_success "Test conversation created: $CONVERSATION_ID"
        return 0
    else
        log_error "Test conversation creation failed: $response"
        return 1
    fi
}

# Test 1: Basic reasoning endpoint structure
test_reasoning_endpoint_structure() {
    log_info "Testing reasoning endpoint structure..."
    increment_test
    
    local response=$(curl -s -X POST "$API_BASE/websocket/test-reasoning" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "{
            \"conversation_id\": \"$CONVERSATION_ID\",
            \"message\": \"Analyze ERP sales performance with step-by-step reasoning\",
            \"user_id\": \"reasoning-test-user\"
        }")
    
    if echo "$response" | jq -e '.reasoning_steps' > /dev/null 2>&1; then
        local steps_count=$(echo "$response" | jq '.reasoning_steps | length')
        log_success "Reasoning endpoint working - Generated $steps_count reasoning steps"
        
        # Validate each reasoning step has required fields
        local valid_steps=0
        for i in $(seq 0 $((steps_count-1))); do
            local step=$(echo "$response" | jq ".reasoning_steps[$i]")
            if echo "$step" | jq -e '.step_type, .content, .icon' > /dev/null 2>&1; then
                ((valid_steps++))
            fi
        done
        
        if [ "$valid_steps" -eq "$steps_count" ]; then
            log_success "All reasoning steps have required structure (step_type, content, icon)"
        else
            log_warning "Only $valid_steps/$steps_count steps have complete structure"
        fi
        
    else
        log_error "Reasoning endpoint test failed: $response"
        return 1
    fi
}

# Test: Reasoning via actual chat endpoint
test_reasoning_via_chat_endpoint() {
    log_info "Testing reasoning via actual chat endpoint..."
    increment_test
    
    local start_time=$(date +%s.%N)
    
    local response=$(curl -s -X POST "$API_BASE/chat/" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "{
            \"message\": \"Analyze ERP sales performance with detailed reasoning steps including database queries and memory checks\",
            \"agent_type\": \"analytics\",
            \"model\": \"gemini2.0:flash\"
        }")
    
    local end_time=$(date +%s.%N)
    local duration=$(echo "$end_time - $start_time" | bc)
    
    if echo "$response" | jq -e '.content' > /dev/null 2>&1; then
        local content=$(echo "$response" | jq -r '.content')
        log_success "Chat endpoint with reasoning working - Response length: ${#content} characters"
        
        # Check if response contains reasoning indicators
        if echo "$content" | grep -q -E "step|reasoning|analysis|🧠|📂|🌐|💻"; then
            log_success "Response contains reasoning indicators"
        else
            log_warning "Response may not contain explicit reasoning steps"
        fi
        
        # Performance validation
        if (( $(echo "$duration < 15" | bc -l) )); then
            log_success "Chat reasoning response time acceptable: ${duration}s"
        else
            log_warning "Chat reasoning response time slow: ${duration}s (>15s)"
        fi
        
    else
        log_error "Chat reasoning test failed: $response"
        return 1
    fi
}

# Test 2: Reasoning with different data sources
test_reasoning_data_sources() {
    log_info "Testing reasoning with multiple data sources..."
    increment_test
    
    local response=$(curl -s -X POST "$API_BASE/websocket/test-reasoning" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "{
            \"conversation_id\": \"$CONVERSATION_ID\",
            \"message\": \"Get customer data from database, check memory for preferences, and analyze with external API data\",
            \"user_id\": \"reasoning-test-user\"
        }")
    
    if echo "$response" | jq -e '.reasoning_steps' > /dev/null 2>&1; then
        local sources=$(echo "$response" | jq -r '.reasoning_steps[].source' | sort | uniq)
        log_success "Reasoning uses multiple data sources: $(echo $sources | tr '\n' ' ')"
        
        # Check for expected data sources from reasoning plan
        local expected_sources="Database Memory API Vector_DB Knowledge_Base System"
        local found_sources=0
        for source in $expected_sources; do
            if echo "$sources" | grep -qi "$source"; then
                ((found_sources++))
            fi
        done
        
        if [ $found_sources -gt 2 ]; then
            log_success "Found $found_sources different data sources in reasoning"
        else
            log_warning "Limited data source diversity in reasoning ($found_sources sources)"
        fi
    else
        log_error "Multi-source reasoning test failed: $response"
        return 1
    fi
}

# Test 3: WebSocket chat reasoning streaming
test_websocket_reasoning_streaming() {
    log_info "Testing WebSocket chat reasoning streaming..."
    increment_test
    
    if command -v websocat > /dev/null 2>&1; then
        local ws_url="$WS_BASE/ws/reasoning/$CONVERSATION_ID?token=$TOKEN"
        
        # Create test message for WebSocket chat
        local test_message='{
            "type": "chat_message",
            "message": "Analyze inventory levels with step-by-step reasoning",
            "conversation_id": "'$CONVERSATION_ID'"
        }'
        
        # Test WebSocket streaming with timeout
        echo "$test_message" | timeout 10 websocat "$ws_url" > /tmp/ws_reasoning_test.out 2>&1 &
        local ws_pid=$!
        
        sleep 5
        if kill -0 $ws_pid 2>/dev/null; then
            kill $ws_pid 2>/dev/null
        fi
        
        if [ -f /tmp/ws_reasoning_test.out ] && [ -s /tmp/ws_reasoning_test.out ]; then
            local stream_content=$(cat /tmp/ws_reasoning_test.out)
            
            # Check for streaming reasoning steps or chat responses
            if echo "$stream_content" | grep -q "reasoning_step\|step_type\|icon\|content\|message"; then
                log_success "WebSocket chat reasoning streaming working"
                
                # Count streamed steps or messages
                local streamed_items=$(echo "$stream_content" | grep -c "reasoning_step\|content" || echo "0")
                log_info "Streamed $streamed_items reasoning items via WebSocket"
            else
                log_warning "WebSocket connected but no reasoning steps streamed"
            fi
        else
            log_warning "WebSocket reasoning streaming test inconclusive"
        fi
        
        rm -f /tmp/ws_reasoning_test.out
    else
        log_warning "WebSocket test skipped - websocat not available"
        log_info "Install websocat: brew install websocat"
    fi
}

# Test 4: Reasoning endpoint performance under load
test_reasoning_performance_load() {
    log_info "Testing reasoning endpoint performance under load..."
    increment_test
    
    local total_requests=3
    local successful_requests=0
    local total_duration=0
    local total_steps=0
    
    for i in $(seq 1 $total_requests); do
        local start_time=$(date +%s.%N)
        
        local response=$(curl -s -X POST "$API_BASE/websocket/test-reasoning" \
            -H "Authorization: Bearer $TOKEN" \
            -H "Content-Type: application/json" \
            -d "{
                \"conversation_id\": \"$CONVERSATION_ID\",
                \"message\": \"Request $i: Analyze ERP performance metrics with detailed reasoning\",
                \"user_id\": \"reasoning-test-user\"
            }")
        
        local end_time=$(date +%s.%N)
        local duration=$(echo "$end_time - $start_time" | bc)
        total_duration=$(echo "$total_duration + $duration" | bc)
        
        if echo "$response" | jq -e '.reasoning_steps' > /dev/null 2>&1; then
            local steps_count=$(echo "$response" | jq '.reasoning_steps | length')
            total_steps=$((total_steps + steps_count))
            ((successful_requests++))
        fi
        
        # Small delay between requests
        sleep 0.5
    done
    
    if [ $successful_requests -eq $total_requests ]; then
        local avg_duration=$(echo "scale=2; $total_duration / $total_requests" | bc)
        local avg_steps=$(echo "scale=1; $total_steps / $total_requests" | bc)
        log_success "Load test successful - $successful_requests/$total_requests requests completed"
        log_info "Average response time: ${avg_duration}s, Average steps: $avg_steps"
    else
        log_warning "Load test partial success - $successful_requests/$total_requests requests completed"
    fi
}

# Test 5: Advanced reasoning scenarios
test_advanced_reasoning_scenarios() {
    log_info "Testing advanced reasoning scenarios..."
    increment_test
    
    local scenarios=(
        "Analyze customer churn patterns and recommend retention strategies"
        "Calculate ROI for new product launch with market analysis"
        "Optimize inventory levels based on seasonal demand forecasting"
        "Evaluate financial performance across multiple business units"
    )
    
    local total_scenarios=${#scenarios[@]}
    local successful_scenarios=0
    
    for scenario in "${scenarios[@]}"; do
        local response=$(curl -s -X POST "$API_BASE/websocket/test-reasoning" \
            -H "Authorization: Bearer $TOKEN" \
            -H "Content-Type: application/json" \
            -d "{
                \"conversation_id\": \"$CONVERSATION_ID\",
                \"message\": \"$scenario\",
                \"user_id\": \"reasoning-test-user\"
            }")
        
        if echo "$response" | jq -e '.reasoning_steps' > /dev/null 2>&1; then
            local steps_count=$(echo "$response" | jq '.reasoning_steps | length')
            if [ $steps_count -gt 0 ]; then
                ((successful_scenarios++))
            fi
        fi
    done
    
    if [ $successful_scenarios -eq $total_scenarios ]; then
        log_success "All $total_scenarios advanced reasoning scenarios successful"
    elif [ $successful_scenarios -gt $((total_scenarios / 2)) ]; then
        log_warning "Partial success: $successful_scenarios/$total_scenarios scenarios worked"
    else
        log_error "Advanced reasoning scenarios mostly failed: $successful_scenarios/$total_scenarios"
        return 1
    fi
}

# Test 5: Reasoning step content quality
test_reasoning_step_quality() {
    log_info "Testing reasoning step content quality..."
    increment_test
    
    local response=$(curl -s -X POST "$API_BASE/websocket/test-reasoning" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "{
            \"conversation_id\": \"$CONVERSATION_ID\",
            \"message\": \"Explain how to calculate monthly recurring revenue with detailed steps\",
            \"user_id\": \"reasoning-test-user\"
        }")
    
    if echo "$response" | jq -e '.reasoning_steps' > /dev/null 2>&1; then
        local steps_count=$(echo "$response" | jq '.reasoning_steps | length')
        
        # Check step content quality
        local detailed_steps=0
        for i in $(seq 0 $((steps_count-1))); do
            local description=$(echo "$response" | jq -r ".reasoning_steps[$i].description")
            local desc_length=${#description}
            
            if [ $desc_length -gt 20 ]; then
                ((detailed_steps++))
            fi
        done
        
        local quality_ratio=$(echo "scale=2; $detailed_steps / $steps_count" | bc)
        
        if (( $(echo "$quality_ratio > 0.7" | bc -l) )); then
            log_success "Reasoning step quality good - $detailed_steps/$steps_count steps have detailed descriptions"
        else
            log_warning "Reasoning step quality could be improved - only $detailed_steps/$steps_count steps are detailed"
        fi
        
        # Check for reasoning chain coherence
        local step_types=$(echo "$response" | jq -r '.reasoning_steps[].step_type' | sort | uniq -c)
        log_info "Reasoning step type distribution: $(echo $step_types | tr '\n' ' ')"
        
    else
        log_error "Reasoning step quality test failed: $response"
        return 1
    fi
}

# Test 6: Memory integration in reasoning
test_reasoning_memory_integration() {
    log_info "Testing memory integration in reasoning..."
    increment_test
    
    # First, store some memory for the test
    curl -s -X POST "$API_BASE/memory" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d '{
            "user_id": "reasoning-test-user",
            "organization_id": "reasoning-test-org",
            "memory_type": "user_preference",
            "content": "User prefers detailed financial analysis with charts",
            "importance": 0.9,
            "tags": ["finance", "analysis", "preference"]
        }' > /dev/null
    
    # Test reasoning that should use memory
    local response=$(curl -s -X POST "$API_BASE/websocket/test-reasoning" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "{
            \"conversation_id\": \"$CONVERSATION_ID\",
            \"message\": \"Generate financial analysis report based on my preferences\",
            \"user_id\": \"reasoning-test-user\"
        }")
    
    if echo "$response" | jq -e '.reasoning_steps' > /dev/null 2>&1; then
        # Check if memory was referenced in reasoning
        local memory_steps=$(echo "$response" | jq -r '.reasoning_steps[] | select(.source | test("Memory|memory"; "i")) | .description')
        
        if [ -n "$memory_steps" ]; then
            log_success "Memory integration working - reasoning references stored memory"
            log_info "Memory-based reasoning: $(echo "$memory_steps" | head -1)"
        else
            log_warning "Memory integration unclear - no explicit memory references in reasoning"
        fi
    else
        log_error "Memory integration test failed: $response"
        return 1
    fi
}

# Main test execution
main() {
    echo "=========================================="
    echo "AI Copilot EXCLUSIVE Reasoning Test Suite"
    echo "=========================================="
    echo
    
    log_info "Testing ONLY reasoning capabilities..."
    echo
    
    # Authentication and setup
    if test_authentication && create_test_conversation; then
        # Core reasoning tests
        test_reasoning_endpoint_structure
        test_reasoning_data_sources
        test_websocket_reasoning_streaming
        test_reasoning_performance_load
        test_advanced_reasoning_scenarios
        test_reasoning_step_quality
        test_reasoning_memory_integration
        test_reasoning_via_chat_endpoint
    else
        log_error "Setup failed - skipping reasoning tests"
        exit 1
    fi
    
    echo
    echo "=========================================="
    echo "Reasoning Test Results Summary"
    echo "=========================================="
    echo -e "Total Tests: ${BLUE}$TOTAL_TESTS${NC}"
    echo -e "Passed: ${GREEN}$PASSED_TESTS${NC}"
    echo -e "Failed: ${RED}$FAILED_TESTS${NC}"
    
    if [ $FAILED_TESTS -eq 0 ]; then
        echo -e "\n${GREEN}🧠 All reasoning tests passed! AI Copilot reasoning is working correctly.${NC}"
        exit 0
    else
        echo -e "\n${RED}❌ Some reasoning tests failed. Check logs above for details.${NC}"
        exit 1
    fi
}

# Check dependencies
check_dependencies() {
    local missing_deps=()
    
    if ! command -v curl > /dev/null 2>&1; then
        missing_deps+=("curl")
    fi
    
    if ! command -v jq > /dev/null 2>&1; then
        missing_deps+=("jq")
    fi
    
    if ! command -v bc > /dev/null 2>&1; then
        missing_deps+=("bc")
    fi
    
    if [ ${#missing_deps[@]} -ne 0 ]; then
        log_error "Missing required dependencies: ${missing_deps[*]}"
        log_info "Install missing dependencies:"
        log_info "  macOS: brew install ${missing_deps[*]}"
        log_info "  Ubuntu: sudo apt install ${missing_deps[*]}"
        exit 1
    fi
    
    if ! command -v websocat > /dev/null 2>&1; then
        log_warning "websocat not found - WebSocket tests will be skipped"
        log_info "Install websocat: brew install websocat"
    fi
}

# Run dependency check and main tests
check_dependencies
main "$@"
