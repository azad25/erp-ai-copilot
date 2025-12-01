#!/bin/bash
# Bulk Tool Conversion Script
# Converts multiple tools to MCP format using the generator

set -e

echo "🚀 Bulk Tool Conversion to MCP Format"
echo "======================================"

# ERP API Tools
echo ""
echo "Converting ERP API tools..."
python scripts/generate_mcp_tool.py --name "Get Users" --server "erp-api" --description "Retrieve users from ERP system" --category "ERP"
python scripts/generate_mcp_tool.py --name "Create Order" --server "erp-api" --description "Create new order in ERP system" --category "ERP"
python scripts/generate_mcp_tool.py --name "Update Product" --server "erp-api" --description "Update product information" --category "ERP"
python scripts/generate_mcp_tool.py --name "Get Customers" --server "erp-api" --description "Retrieve customer list" --category "ERP"

# Analytics Tools
echo ""
echo "Converting Analytics tools..."
python scripts/generate_mcp_tool.py --name "Generate Report" --server "analytics" --description "Generate analytics report" --category "Analytics"
python scripts/generate_mcp_tool.py --name "Create Chart" --server "analytics" --description "Create data visualization chart" --category "Analytics"

# Communication Tools
echo ""
echo "Converting Communication tools..."
python scripts/generate_mcp_tool.py --name "Send Email" --server "communication" --description "Send email notification" --category "Communication"
python scripts/generate_mcp_tool.py --name "Send Notification" --server "communication" --description "Send system notification" --category "Communication"

echo ""
echo "✅ Bulk conversion complete!"
echo "Run 'python validate_phase4.py' to verify"
