# Microservice Integration Guide

## Overview

This guide provides step-by-step instructions for integrating a new microservice with the ERP API Gateway. The gateway supports multiple communication protocols (REST, GraphQL, WebSocket, gRPC) and provides real-time capabilities, authentication, authorization, caching, and event publishing.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Service Registration](#service-registration)
3. [Protocol Buffer Definition](#protocol-buffer-definition)
4. [gRPC Client Integration](#grpc-client-integration)
5. [REST API Integration](#rest-api-integration)
6. [GraphQL Integration](#graphql-integration)
7. [WebSocket Real-time Integration](#websocket-real-time-integration)
8. [Authentication & Authorization](#authentication--authorization)
9. [Caching Strategy](#caching-strategy)
10. [Event Publishing](#event-publishing)
11. [Testing Integration](#testing-integration)
12. [Deployment Configuration](#deployment-configuration)

## Prerequisites

Before integrating a new microservice, ensure you have:

- Go 1.23+ installed
- Protocol Buffers compiler (protoc) installed
- Access to the microservice's gRPC interface
- Understanding of the service's data models and operations
- Knowledge of required permissions and roles

## Example: Integrating Inventory Service

Throughout this guide, we'll use an "Inventory Service" as an example to demonstrate the integration process.

### Service Specifications
- **Service Name**: Inventory Service
- **gRPC Port**: 50055
- **Domain**: Inventory management (products, stock, warehouses)
- **Key Operations**: CRUD operations on products, stock management, warehouse operations
- **Real-time Features**: Stock level updates, low stock alerts
- **Permissions**: `read:inventory`, `write:inventory`, `manage:warehouses`#
# Step 1: Service Registration

### 1.1 Update Configuration

Add the new service to the configuration structure:

```go
// internal/config/config.go
type GRPCConfig struct {
    Services map[string]ServiceConfig `yaml:"services"`
}

// Add to default configuration
func getDefaultGRPCConfig() GRPCConfig {
    return GRPCConfig{
        Services: map[string]ServiceConfig{
            "auth":      {Address: "auth-service:50051", Timeout: 10 * time.Second},
            "crm":       {Address: "crm-service:50052", Timeout: 10 * time.Second},
            "hrm":       {Address: "hrm-service:50053", Timeout: 10 * time.Second},
            "finance":   {Address: "finance-service:50054", Timeout: 10 * time.Second},
            "inventory": {Address: "inventory-service:50055", Timeout: 10 * time.Second}, // New service
        },
    }
}
```

### 1.2 Update Environment Variables

Add environment variable support:

```bash
# Environment variables
GRPC_SERVICES_INVENTORY_ADDRESS=inventory-service:50055
GRPC_SERVICES_INVENTORY_TIMEOUT=10s
GRPC_SERVICES_INVENTORY_MAX_RETRIES=3
```

### 1.3 Update Configuration File

```yaml
# config.yaml
grpc:
  services:
    inventory:
      address: "inventory-service:50055"
      timeout: "10s"
      max_retries: 3
      pool_size: 10
```## Step 2
: Protocol Buffer Definition

### 2.1 Create Proto File

Create the Protocol Buffer definition for the Inventory Service:

```protobuf
// proto/inventory/inventory.proto
syntax = "proto3";

package inventory;

option go_package = "github.com/your-org/erp-api-gateway/proto/inventory";

import "google/protobuf/timestamp.proto";
import "proto/common/common.proto";

// Inventory Service Definition
service InventoryService {
  // Product operations
  rpc GetProducts(GetProductsRequest) returns (GetProductsResponse);
  rpc GetProduct(GetProductRequest) returns (GetProductResponse);
  rpc CreateProduct(CreateProductRequest) returns (CreateProductResponse);
  rpc UpdateProduct(UpdateProductRequest) returns (UpdateProductResponse);
  rpc DeleteProduct(DeleteProductRequest) returns (DeleteProductResponse);
  
  // Stock operations
  rpc GetStock(GetStockRequest) returns (GetStockResponse);
  rpc UpdateStock(UpdateStockRequest) returns (UpdateStockResponse);
  rpc GetStockHistory(GetStockHistoryRequest) returns (GetStockHistoryResponse);
  
  // Warehouse operations
  rpc GetWarehouses(GetWarehousesRequest) returns (GetWarehousesResponse);
  rpc CreateWarehouse(CreateWarehouseRequest) returns (CreateWarehouseResponse);
}

// Data Models
message Product {
  string id = 1;
  string name = 2;
  string description = 3;
  string sku = 4;
  double price = 5;
  string category_id = 6;
  google.protobuf.Timestamp created_at = 7;
  google.protobuf.Timestamp updated_at = 8;
}

message Stock {
  string id = 1;
  string product_id = 2;
  string warehouse_id = 3;
  int32 quantity = 4;
  int32 reserved_quantity = 5;
  int32 available_quantity = 6;
  google.protobuf.Timestamp last_updated = 7;
}
```m
essage Warehouse {
  string id = 1;
  string name = 2;
  string address = 3;
  string manager_id = 4;
  bool active = 5;
  google.protobuf.Timestamp created_at = 6;
}

// Request/Response Messages
message GetProductsRequest {
  int32 page = 1;
  int32 limit = 2;
  string search = 3;
  string category_id = 4;
  string sort_by = 5;
  string sort_order = 6;
}

message GetProductsResponse {
  bool success = 1;
  string message = 2;
  repeated Product data = 3;
  common.PaginationMeta meta = 4;
  map<string, common.FieldErrors> errors = 5;
}

message CreateProductRequest {
  string name = 1;
  string description = 2;
  string sku = 3;
  double price = 4;
  string category_id = 5;
}

message CreateProductResponse {
  bool success = 1;
  string message = 2;
  Product data = 3;
  map<string, common.FieldErrors> errors = 4;
}

message UpdateStockRequest {
  string product_id = 1;
  string warehouse_id = 2;
  int32 quantity_change = 3;
  string reason = 4;
  string user_id = 5;
}
```

### 2.2 Generate Go Code

```bash
# Generate Go code from proto files
protoc --go_out=. --go-grpc_out=. proto/inventory/inventory.proto

# Or use Makefile
make proto-gen
```## 
Step 3: gRPC Client Integration

### 3.1 Update gRPC Client Service

Add the new service to the gRPC client:

```go
// internal/services/grpc_client/grpc_client.go
import (
    inventorypb "github.com/your-org/erp-api-gateway/proto/inventory"
)

type Client struct {
    connections map[string]*grpc.ClientConn
    config      *config.GRPCConfig
    logger      *logging.Logger
    metrics     *metrics.GRPCMetrics
    circuitBreakers map[string]*CircuitBreaker
}

// Add inventory service client method
func (c *Client) InventoryService() inventorypb.InventoryServiceClient {
    conn := c.getConnection("inventory")
    return inventorypb.NewInventoryServiceClient(conn)
}

// Add service health check
func (c *Client) CheckInventoryHealth(ctx context.Context) error {
    client := c.InventoryService()
    
    // Use a simple health check call
    _, err := client.GetWarehouses(ctx, &inventorypb.GetWarehousesRequest{
        Page:  1,
        Limit: 1,
    })
    
    return err
}
```

### 3.2 Update Health Checks

Add the new service to health check endpoints:

```go
// internal/server/server.go
func (s *Server) readinessHandler(c *gin.Context) {
    dependencies := map[string]string{
        "redis":     "healthy",
        "kafka":     "healthy",
        "auth_service":      "healthy",
        "crm_service":       "healthy",
        "inventory_service": "healthy", // Add new service
    }
    
    // Check inventory service health
    if err := s.container.GRPCClient.CheckInventoryHealth(c.Request.Context()); err != nil {
        dependencies["inventory_service"] = "unhealthy"
        c.JSON(503, gin.H{
            "status": "not_ready",
            "timestamp": time.Now().UTC(),
            "dependencies": dependencies,
        })
        return
    }
    
    c.JSON(200, gin.H{
        "status": "ready",
        "timestamp": time.Now().UTC(),
        "dependencies": dependencies,
    })
}
```#
# Step 4: REST API Integration

### 4.1 Create REST Handler

Create a new REST handler for the inventory service:

```go
// api/rest/inventory_handler.go
package rest

import (
    "context"
    "net/http"
    "strconv"
    "time"

    "github.com/gin-gonic/gin"
    inventorypb "github.com/your-org/erp-api-gateway/proto/inventory"
    "github.com/your-org/erp-api-gateway/internal/services/grpc_client"
    "github.com/your-org/erp-api-gateway/internal/services/redis"
    "github.com/your-org/erp-api-gateway/internal/services/kafka"
    "github.com/your-org/erp-api-gateway/internal/logging"
)

type InventoryHandler struct {
    grpcClient    *grpc_client.Client
    redisClient   *redis.Client
    kafkaProducer *kafka.Producer
    logger        *logging.Logger
}

func NewInventoryHandler(container *Container) *InventoryHandler {
    return &InventoryHandler{
        grpcClient:    container.GRPCClient,
        redisClient:   container.RedisClient,
        kafkaProducer: container.KafkaProducer,
        logger:        container.Logger,
    }
}

// GetProducts handles GET /api/v1/inventory/products/
func (h *InventoryHandler) GetProducts(c *gin.Context) {
    // Parse query parameters
    page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
    limit, _ := strconv.Atoi(c.DefaultQuery("limit", "20"))
    search := c.Query("search")
    categoryID := c.Query("category_id")
    sortBy := c.DefaultQuery("sort_by", "created_at")
    sortOrder := c.DefaultQuery("sort_order", "desc")

    // Check cache first
    cacheKey := fmt.Sprintf("products:page:%d:limit:%d:search:%s:category:%s", 
        page, limit, search, categoryID)
    
    if cached, err := h.redisClient.Get(c.Request.Context(), cacheKey); err == nil {
        var response map[string]interface{}
        if json.Unmarshal(cached, &response) == nil {
            c.JSON(200, response)
            return
        }
    }

    // Make gRPC call
    client := h.grpcClient.InventoryService()
    resp, err := client.GetProducts(c.Request.Context(), &inventorypb.GetProductsRequest{
        Page:       int32(page),
        Limit:      int32(limit),
        Search:     search,
        CategoryId: categoryID,
        SortBy:     sortBy,
        SortOrder:  sortOrder,
    })

    if err != nil {
        h.logger.Error("Failed to get products", "error", err)
        c.JSON(500, gin.H{
            "success": false,
            "message": "Failed to retrieve products",
            "errors":  map[string][]string{},
        })
        return
    }

    // Convert gRPC response to REST format
    response := h.convertProductsResponse(resp)
    
    // Cache the response
    if responseData, err := json.Marshal(response); err == nil {
        h.redisClient.Set(c.Request.Context(), cacheKey, responseData, 5*time.Minute)
    }

    c.JSON(200, response)
}
```// 
CreateProduct handles POST /api/v1/inventory/products/
func (h *InventoryHandler) CreateProduct(c *gin.Context) {
    var req CreateProductRequest
    if err := c.ShouldBindJSON(&req); err != nil {
        c.JSON(400, gin.H{
            "success": false,
            "message": "Invalid request data",
            "errors":  parseValidationErrors(err),
        })
        return
    }

    // Get user claims for audit
    userClaims := getUserClaims(c)

    // Make gRPC call
    client := h.grpcClient.InventoryService()
    resp, err := client.CreateProduct(c.Request.Context(), &inventorypb.CreateProductRequest{
        Name:        req.Name,
        Description: req.Description,
        Sku:         req.SKU,
        Price:       req.Price,
        CategoryId:  req.CategoryID,
    })

    if err != nil {
        h.logger.Error("Failed to create product", "error", err, "user_id", userClaims.UserID)
        c.JSON(500, gin.H{
            "success": false,
            "message": "Failed to create product",
            "errors":  map[string][]string{},
        })
        return
    }

    // Publish business event
    if resp.Success {
        event := map[string]interface{}{
            "event_type": "ProductCreated",
            "product_id": resp.Data.Id,
            "user_id":    userClaims.UserID,
            "timestamp":  time.Now().UTC(),
            "data": map[string]interface{}{
                "name": resp.Data.Name,
                "sku":  resp.Data.Sku,
            },
        }
        
        h.kafkaProducer.PublishEvent(c.Request.Context(), "inventory.product.created", event)
        
        // Publish real-time notification
        notification := map[string]interface{}{
            "type":    "product_created",
            "message": fmt.Sprintf("New product '%s' has been created", resp.Data.Name),
            "data":    resp.Data,
        }
        h.redisClient.Publish(c.Request.Context(), "inventory:notifications", notification)
    }

    // Convert and return response
    response := h.convertCreateProductResponse(resp)
    c.JSON(201, response)
}

// UpdateStock handles PUT /api/v1/inventory/stock/
func (h *InventoryHandler) UpdateStock(c *gin.Context) {
    var req UpdateStockRequest
    if err := c.ShouldBindJSON(&req); err != nil {
        c.JSON(400, gin.H{
            "success": false,
            "message": "Invalid request data",
            "errors":  parseValidationErrors(err),
        })
        return
    }

    userClaims := getUserClaims(c)

    // Make gRPC call
    client := h.grpcClient.InventoryService()
    resp, err := client.UpdateStock(c.Request.Context(), &inventorypb.UpdateStockRequest{
        ProductId:      req.ProductID,
        WarehouseId:    req.WarehouseID,
        QuantityChange: int32(req.QuantityChange),
        Reason:         req.Reason,
        UserId:         userClaims.UserID,
    })

    if err != nil {
        h.logger.Error("Failed to update stock", "error", err, "user_id", userClaims.UserID)
        c.JSON(500, gin.H{
            "success": false,
            "message": "Failed to update stock",
            "errors":  map[string][]string{},
        })
        return
    }

    // Publish real-time stock update
    if resp.Success {
        stockUpdate := map[string]interface{}{
            "type":         "stock_updated",
            "product_id":   req.ProductID,
            "warehouse_id": req.WarehouseID,
            "new_quantity": resp.Data.Quantity,
            "change":       req.QuantityChange,
            "timestamp":    time.Now().UTC(),
        }
        
        // Publish to product-specific channel
        productChannel := fmt.Sprintf("inventory:product:%s", req.ProductID)
        h.redisClient.Publish(c.Request.Context(), productChannel, stockUpdate)
        
        // Publish to general inventory channel
        h.redisClient.Publish(c.Request.Context(), "inventory:stock_updates", stockUpdate)
        
        // Publish business event to Kafka
        h.kafkaProducer.PublishEvent(c.Request.Context(), "inventory.stock.updated", stockUpdate)
    }

    response := h.convertUpdateStockResponse(resp)
    c.JSON(200, response)
}
```###
 4.2 Register REST Routes

Add the inventory routes to the server:

```go
// internal/server/server.go
func (s *Server) setupRoutes() {
    // ... existing routes ...

    // Inventory API routes
    inventoryGroup := s.router.Group("/api/v1/inventory")
    inventoryGroup.Use(middleware.RequireAuth(s.container.AuthValidator))
    {
        inventoryHandler := rest.NewInventoryHandler(s.container)
        
        // Product routes
        productGroup := inventoryGroup.Group("/products")
        productGroup.Use(middleware.RequirePermission("read:inventory"))
        {
            productGroup.GET("/", inventoryHandler.GetProducts)
            productGroup.GET("/:id", inventoryHandler.GetProduct)
            
            // Write operations require write permission
            writeGroup := productGroup.Group("")
            writeGroup.Use(middleware.RequirePermission("write:inventory"))
            {
                writeGroup.POST("/", inventoryHandler.CreateProduct)
                writeGroup.PUT("/:id", inventoryHandler.UpdateProduct)
                writeGroup.DELETE("/:id", inventoryHandler.DeleteProduct)
            }
        }
        
        // Stock routes
        stockGroup := inventoryGroup.Group("/stock")
        stockGroup.Use(middleware.RequirePermission("read:inventory"))
        {
            stockGroup.GET("/", inventoryHandler.GetStock)
            stockGroup.GET("/history", inventoryHandler.GetStockHistory)
            
            // Stock updates require write permission
            stockGroup.PUT("/", 
                middleware.RequirePermission("write:inventory"), 
                inventoryHandler.UpdateStock)
        }
        
        // Warehouse routes (require special permission)
        warehouseGroup := inventoryGroup.Group("/warehouses")
        warehouseGroup.Use(middleware.RequirePermission("manage:warehouses"))
        {
            warehouseGroup.GET("/", inventoryHandler.GetWarehouses)
            warehouseGroup.POST("/", inventoryHandler.CreateWarehouse)
            warehouseGroup.PUT("/:id", inventoryHandler.UpdateWarehouse)
            warehouseGroup.DELETE("/:id", inventoryHandler.DeleteWarehouse)
        }
    }
}
```

### 4.3 Request/Response Models

Define REST API models:

```go
// api/rest/inventory_models.go
package rest

import "time"

// Request models
type CreateProductRequest struct {
    Name        string  `json:"name" binding:"required,min=1,max=255"`
    Description string  `json:"description" binding:"max=1000"`
    SKU         string  `json:"sku" binding:"required,min=1,max=100"`
    Price       float64 `json:"price" binding:"required,min=0"`
    CategoryID  string  `json:"category_id" binding:"required"`
}

type UpdateStockRequest struct {
    ProductID       string `json:"product_id" binding:"required"`
    WarehouseID     string `json:"warehouse_id" binding:"required"`
    QuantityChange  int    `json:"quantity_change" binding:"required"`
    Reason          string `json:"reason" binding:"required,max=255"`
}

// Response models
type Product struct {
    ID          string    `json:"id"`
    Name        string    `json:"name"`
    Description string    `json:"description"`
    SKU         string    `json:"sku"`
    Price       float64   `json:"price"`
    CategoryID  string    `json:"category_id"`
    CreatedAt   time.Time `json:"created_at"`
    UpdatedAt   time.Time `json:"updated_at"`
}

type Stock struct {
    ID                string    `json:"id"`
    ProductID         string    `json:"product_id"`
    WarehouseID       string    `json:"warehouse_id"`
    Quantity          int       `json:"quantity"`
    ReservedQuantity  int       `json:"reserved_quantity"`
    AvailableQuantity int       `json:"available_quantity"`
    LastUpdated       time.Time `json:"last_updated"`
}
```## Step 5
: GraphQL Integration

### 5.1 Update GraphQL Schema

Add inventory types to the GraphQL schema:

```graphql
# api/graphql/schema/inventory.graphql
extend type Query {
  products(
    page: Int = 1
    limit: Int = 20
    search: String
    categoryId: String
    sortBy: String = "created_at"
    sortOrder: String = "desc"
  ): ProductConnection!
  
  product(id: ID!): Product
  
  stock(productId: ID!, warehouseId: ID!): Stock
  
  warehouses(
    page: Int = 1
    limit: Int = 20
    active: Boolean
  ): WarehouseConnection!
}

extend type Mutation {
  createProduct(input: CreateProductInput!): CreateProductPayload!
  updateProduct(id: ID!, input: UpdateProductInput!): UpdateProductPayload!
  deleteProduct(id: ID!): DeleteProductPayload!
  
  updateStock(input: UpdateStockInput!): UpdateStockPayload!
  
  createWarehouse(input: CreateWarehouseInput!): CreateWarehousePayload!
}

extend type Subscription {
  stockUpdates(productId: ID): StockUpdate!
  lowStockAlerts: LowStockAlert!
  inventoryNotifications: InventoryNotification!
}

# Types
type Product {
  id: ID!
  name: String!
  description: String
  sku: String!
  price: Float!
  categoryId: String!
  category: Category
  stock: [Stock!]!
  createdAt: Time!
  updatedAt: Time!
}

type Stock {
  id: ID!
  productId: ID!
  product: Product!
  warehouseId: ID!
  warehouse: Warehouse!
  quantity: Int!
  reservedQuantity: Int!
  availableQuantity: Int!
  lastUpdated: Time!
}

type Warehouse {
  id: ID!
  name: String!
  address: String!
  managerId: String
  manager: User
  active: Boolean!
  createdAt: Time!
}

# Connections
type ProductConnection {
  edges: [ProductEdge!]!
  pageInfo: PageInfo!
  totalCount: Int!
}

type ProductEdge {
  node: Product!
  cursor: String!
}

# Input types
input CreateProductInput {
  name: String!
  description: String
  sku: String!
  price: Float!
  categoryId: String!
}

input UpdateStockInput {
  productId: ID!
  warehouseId: ID!
  quantityChange: Int!
  reason: String!
}

# Payload types
type CreateProductPayload {
  success: Boolean!
  message: String
  product: Product
  errors: [FieldError!]
}

type UpdateStockPayload {
  success: Boolean!
  message: String
  stock: Stock
  errors: [FieldError!]
}

# Subscription types
type StockUpdate {
  productId: ID!
  warehouseId: ID!
  newQuantity: Int!
  change: Int!
  timestamp: Time!
}

type LowStockAlert {
  productId: ID!
  product: Product!
  warehouseId: ID!
  warehouse: Warehouse!
  currentQuantity: Int!
  threshold: Int!
  timestamp: Time!
}

type InventoryNotification {
  type: String!
  message: String!
  data: JSON
  timestamp: Time!
}
```### 
5.2 Implement GraphQL Resolvers

Create resolvers for the inventory schema:

```go
// api/graphql/resolvers/inventory_resolver.go
package resolvers

import (
    "context"
    "fmt"
    "strconv"

    inventorypb "github.com/your-org/erp-api-gateway/proto/inventory"
    "github.com/your-org/erp-api-gateway/api/graphql/model"
)

// Query resolvers
func (r *queryResolver) Products(ctx context.Context, page *int, limit *int, search *string, categoryID *string, sortBy *string, sortOrder *string) (*model.ProductConnection, error) {
    // Check permissions
    if err := r.checkPermission(ctx, "read:inventory"); err != nil {
        return nil, err
    }

    // Set defaults
    if page == nil {
        defaultPage := 1
        page = &defaultPage
    }
    if limit == nil {
        defaultLimit := 20
        limit = &defaultLimit
    }

    // Create DataLoader key for batching
    key := fmt.Sprintf("products:page:%d:limit:%d", *page, *limit)
    if search != nil {
        key += ":search:" + *search
    }
    if categoryID != nil {
        key += ":category:" + *categoryID
    }

    // Use DataLoader to batch requests
    result, err := r.productLoader.Load(ctx, key)
    if err != nil {
        return nil, err
    }

    return result.(*model.ProductConnection), nil
}

func (r *queryResolver) Product(ctx context.Context, id string) (*model.Product, error) {
    if err := r.checkPermission(ctx, "read:inventory"); err != nil {
        return nil, err
    }

    // Use DataLoader for single product
    result, err := r.singleProductLoader.Load(ctx, id)
    if err != nil {
        return nil, err
    }

    return result.(*model.Product), nil
}

func (r *queryResolver) Stock(ctx context.Context, productID string, warehouseID string) (*model.Stock, error) {
    if err := r.checkPermission(ctx, "read:inventory"); err != nil {
        return nil, err
    }

    client := r.grpcClient.InventoryService()
    resp, err := client.GetStock(ctx, &inventorypb.GetStockRequest{
        ProductId:   productID,
        WarehouseId: warehouseID,
    })

    if err != nil {
        return nil, fmt.Errorf("failed to get stock: %w", err)
    }

    if !resp.Success {
        return nil, fmt.Errorf("failed to get stock: %s", resp.Message)
    }

    return convertStockFromProto(resp.Data), nil
}

// Mutation resolvers
func (r *mutationResolver) CreateProduct(ctx context.Context, input model.CreateProductInput) (*model.CreateProductPayload, error) {
    if err := r.checkPermission(ctx, "write:inventory"); err != nil {
        return &model.CreateProductPayload{
            Success: false,
            Message: stringPtr("Insufficient permissions"),
        }, nil
    }

    userClaims := getUserClaims(ctx)

    client := r.grpcClient.InventoryService()
    resp, err := client.CreateProduct(ctx, &inventorypb.CreateProductRequest{
        Name:        input.Name,
        Description: stringValue(input.Description),
        Sku:         input.Sku,
        Price:       input.Price,
        CategoryId:  input.CategoryID,
    })

    if err != nil {
        r.logger.Error("Failed to create product via GraphQL", "error", err, "user_id", userClaims.UserID)
        return &model.CreateProductPayload{
            Success: false,
            Message: stringPtr("Failed to create product"),
        }, nil
    }

    payload := &model.CreateProductPayload{
        Success: resp.Success,
        Message: stringPtr(resp.Message),
    }

    if resp.Success && resp.Data != nil {
        payload.Product = convertProductFromProto(resp.Data)
        
        // Publish real-time update
        r.publishProductCreated(ctx, resp.Data, userClaims.UserID)
    }

    if len(resp.Errors) > 0 {
        payload.Errors = convertFieldErrorsFromProto(resp.Errors)
    }

    return payload, nil
}

func (r *mutationResolver) UpdateStock(ctx context.Context, input model.UpdateStockInput) (*model.UpdateStockPayload, error) {
    if err := r.checkPermission(ctx, "write:inventory"); err != nil {
        return &model.UpdateStockPayload{
            Success: false,
            Message: stringPtr("Insufficient permissions"),
        }, nil
    }

    userClaims := getUserClaims(ctx)

    client := r.grpcClient.InventoryService()
    resp, err := client.UpdateStock(ctx, &inventorypb.UpdateStockRequest{
        ProductId:      input.ProductID,
        WarehouseId:    input.WarehouseID,
        QuantityChange: int32(input.QuantityChange),
        Reason:         input.Reason,
        UserId:         userClaims.UserID,
    })

    if err != nil {
        r.logger.Error("Failed to update stock via GraphQL", "error", err, "user_id", userClaims.UserID)
        return &model.UpdateStockPayload{
            Success: false,
            Message: stringPtr("Failed to update stock"),
        }, nil
    }

    payload := &model.UpdateStockPayload{
        Success: resp.Success,
        Message: stringPtr(resp.Message),
    }

    if resp.Success && resp.Data != nil {
        payload.Stock = convertStockFromProto(resp.Data)
        
        // Publish real-time stock update
        r.publishStockUpdate(ctx, resp.Data, input.QuantityChange)
    }

    return payload, nil
}
```### 5.3 
Implement GraphQL Subscriptions

Add subscription resolvers for real-time updates:

```go
// Subscription resolvers
func (r *subscriptionResolver) StockUpdates(ctx context.Context, productID *string) (<-chan *model.StockUpdate, error) {
    if err := r.checkPermission(ctx, "read:inventory"); err != nil {
        return nil, err
    }

    ch := make(chan *model.StockUpdate, 1)

    // Determine subscription channel
    var redisChannel string
    if productID != nil {
        redisChannel = fmt.Sprintf("inventory:product:%s", *productID)
    } else {
        redisChannel = "inventory:stock_updates"
    }

    // Subscribe to Redis channel
    pubsub := r.redisClient.Subscribe(ctx, redisChannel)

    go func() {
        defer close(ch)
        defer pubsub.Close()

        for {
            select {
            case <-ctx.Done():
                return
            case msg := <-pubsub.Channel():
                var update map[string]interface{}
                if err := json.Unmarshal([]byte(msg.Payload), &update); err != nil {
                    r.logger.Error("Failed to unmarshal stock update", "error", err)
                    continue
                }

                stockUpdate := &model.StockUpdate{
                    ProductID:   update["product_id"].(string),
                    WarehouseID: update["warehouse_id"].(string),
                    NewQuantity: int(update["new_quantity"].(float64)),
                    Change:      int(update["change"].(float64)),
                    Timestamp:   parseTime(update["timestamp"].(string)),
                }

                select {
                case ch <- stockUpdate:
                case <-ctx.Done():
                    return
                }
            }
        }
    }()

    return ch, nil
}

func (r *subscriptionResolver) LowStockAlerts(ctx context.Context) (<-chan *model.LowStockAlert, error) {
    if err := r.checkPermission(ctx, "read:inventory"); err != nil {
        return nil, err
    }

    ch := make(chan *model.LowStockAlert, 1)
    pubsub := r.redisClient.Subscribe(ctx, "inventory:low_stock_alerts")

    go func() {
        defer close(ch)
        defer pubsub.Close()

        for {
            select {
            case <-ctx.Done():
                return
            case msg := <-pubsub.Channel():
                var alert map[string]interface{}
                if err := json.Unmarshal([]byte(msg.Payload), &alert); err != nil {
                    r.logger.Error("Failed to unmarshal low stock alert", "error", err)
                    continue
                }

                // Load product and warehouse data
                product, _ := r.singleProductLoader.Load(ctx, alert["product_id"].(string))
                warehouse, _ := r.singleWarehouseLoader.Load(ctx, alert["warehouse_id"].(string))

                lowStockAlert := &model.LowStockAlert{
                    ProductID:       alert["product_id"].(string),
                    Product:         product.(*model.Product),
                    WarehouseID:     alert["warehouse_id"].(string),
                    Warehouse:       warehouse.(*model.Warehouse),
                    CurrentQuantity: int(alert["current_quantity"].(float64)),
                    Threshold:       int(alert["threshold"].(float64)),
                    Timestamp:       parseTime(alert["timestamp"].(string)),
                }

                select {
                case ch <- lowStockAlert:
                case <-ctx.Done():
                    return
                }
            }
        }
    }()

    return ch, nil
}

func (r *subscriptionResolver) InventoryNotifications(ctx context.Context) (<-chan *model.InventoryNotification, error) {
    if err := r.checkPermission(ctx, "read:inventory"); err != nil {
        return nil, err
    }

    ch := make(chan *model.InventoryNotification, 1)
    pubsub := r.redisClient.Subscribe(ctx, "inventory:notifications")

    go func() {
        defer close(ch)
        defer pubsub.Close()

        for {
            select {
            case <-ctx.Done():
                return
            case msg := <-pubsub.Channel():
                var notification map[string]interface{}
                if err := json.Unmarshal([]byte(msg.Payload), &notification); err != nil {
                    r.logger.Error("Failed to unmarshal inventory notification", "error", err)
                    continue
                }

                inventoryNotification := &model.InventoryNotification{
                    Type:      notification["type"].(string),
                    Message:   notification["message"].(string),
                    Data:      notification["data"],
                    Timestamp: parseTime(notification["timestamp"].(string)),
                }

                select {
                case ch <- inventoryNotification:
                case <-ctx.Done():
                    return
                }
            }
        }
    }()

    return ch, nil
}
```### 5.
4 DataLoader Implementation

Implement DataLoaders to prevent N+1 queries:

```go
// api/graphql/dataloaders/inventory_loader.go
package dataloaders

import (
    "context"
    "fmt"
    "strings"
    "time"

    "github.com/graph-gophers/dataloader/v7"
    inventorypb "github.com/your-org/erp-api-gateway/proto/inventory"
    "github.com/your-org/erp-api-gateway/api/graphql/model"
)

type InventoryLoaders struct {
    ProductLoader       *dataloader.Loader[string, *model.Product]
    ProductsLoader      *dataloader.Loader[string, *model.ProductConnection]
    StockLoader         *dataloader.Loader[string, *model.Stock]
    WarehouseLoader     *dataloader.Loader[string, *model.Warehouse]
}

func NewInventoryLoaders(grpcClient *grpc_client.Client, redisClient *redis.Client) *InventoryLoaders {
    return &InventoryLoaders{
        ProductLoader: dataloader.NewBatchedLoader(
            func(ctx context.Context, keys []string) []*dataloader.Result[*model.Product] {
                return batchLoadProducts(ctx, grpcClient, keys)
            },
            dataloader.WithCache[string, *model.Product](&dataloader.NoCache[string, *model.Product]{}),
            dataloader.WithWait[string, *model.Product](time.Millisecond),
        ),
        
        ProductsLoader: dataloader.NewBatchedLoader(
            func(ctx context.Context, keys []string) []*dataloader.Result[*model.ProductConnection] {
                return batchLoadProductConnections(ctx, grpcClient, redisClient, keys)
            },
            dataloader.WithWait[string, *model.ProductConnection](time.Millisecond),
        ),
        
        StockLoader: dataloader.NewBatchedLoader(
            func(ctx context.Context, keys []string) []*dataloader.Result[*model.Stock] {
                return batchLoadStock(ctx, grpcClient, keys)
            },
            dataloader.WithWait[string, *model.Stock](time.Millisecond),
        ),
        
        WarehouseLoader: dataloader.NewBatchedLoader(
            func(ctx context.Context, keys []string) []*dataloader.Result[*model.Warehouse] {
                return batchLoadWarehouses(ctx, grpcClient, keys)
            },
            dataloader.WithWait[string, *model.Warehouse](time.Millisecond),
        ),
    }
}

func batchLoadProducts(ctx context.Context, grpcClient *grpc_client.Client, productIDs []string) []*dataloader.Result[*model.Product] {
    results := make([]*dataloader.Result[*model.Product], len(productIDs))
    
    // Group requests to minimize gRPC calls
    client := grpcClient.InventoryService()
    
    // Make batch request (assuming the service supports batch operations)
    resp, err := client.GetProductsBatch(ctx, &inventorypb.GetProductsBatchRequest{
        ProductIds: productIDs,
    })
    
    if err != nil {
        // Return error for all keys
        for i := range results {
            results[i] = &dataloader.Result[*model.Product]{Error: err}
        }
        return results
    }
    
    // Create a map for quick lookup
    productMap := make(map[string]*model.Product)
    for _, product := range resp.Data {
        productMap[product.Id] = convertProductFromProto(product)
    }
    
    // Fill results in the same order as requested
    for i, productID := range productIDs {
        if product, exists := productMap[productID]; exists {
            results[i] = &dataloader.Result[*model.Product]{Data: product}
        } else {
            results[i] = &dataloader.Result[*model.Product]{Error: fmt.Errorf("product not found: %s", productID)}
        }
    }
    
    return results
}

func batchLoadProductConnections(ctx context.Context, grpcClient *grpc_client.Client, redisClient *redis.Client, keys []string) []*dataloader.Result[*model.ProductConnection] {
    results := make([]*dataloader.Result[*model.ProductConnection], len(keys))
    
    for i, key := range keys {
        // Parse key to extract parameters
        params := parseProductConnectionKey(key)
        
        // Check cache first
        if cached, err := redisClient.Get(ctx, "graphql:"+key); err == nil {
            var connection model.ProductConnection
            if json.Unmarshal(cached, &connection) == nil {
                results[i] = &dataloader.Result[*model.ProductConnection]{Data: &connection}
                continue
            }
        }
        
        // Make gRPC call
        client := grpcClient.InventoryService()
        resp, err := client.GetProducts(ctx, &inventorypb.GetProductsRequest{
            Page:       int32(params.Page),
            Limit:      int32(params.Limit),
            Search:     params.Search,
            CategoryId: params.CategoryID,
            SortBy:     params.SortBy,
            SortOrder:  params.SortOrder,
        })
        
        if err != nil {
            results[i] = &dataloader.Result[*model.ProductConnection]{Error: err}
            continue
        }
        
        connection := convertProductConnectionFromProto(resp)
        results[i] = &dataloader.Result[*model.ProductConnection]{Data: connection}
        
        // Cache the result
        if data, err := json.Marshal(connection); err == nil {
            redisClient.Set(ctx, "graphql:"+key, data, 5*time.Minute)
        }
    }
    
    return results
}
```## 
Step 6: WebSocket Real-time Integration

### 6.1 Update WebSocket Handler

Extend the WebSocket handler to support inventory-specific channels:

```go
// api/ws/inventory_handler.go
package ws

import (
    "context"
    "encoding/json"
    "fmt"
    "strings"

    "github.com/gorilla/websocket"
    "github.com/your-org/erp-api-gateway/internal/auth"
)

// InventoryWebSocketHandler handles inventory-specific WebSocket operations
type InventoryWebSocketHandler struct {
    baseHandler *Handler
}

func NewInventoryWebSocketHandler(baseHandler *Handler) *InventoryWebSocketHandler {
    return &InventoryWebSocketHandler{
        baseHandler: baseHandler,
    }
}

// HandleInventorySubscription handles inventory-specific subscription requests
func (h *InventoryWebSocketHandler) HandleInventorySubscription(conn *websocket.Conn, claims *auth.Claims, msg ClientMessage) {
    switch msg.Type {
    case "subscribe_product_updates":
        h.handleProductUpdatesSubscription(conn, claims, msg)
    case "subscribe_stock_updates":
        h.handleStockUpdatesSubscription(conn, claims, msg)
    case "subscribe_low_stock_alerts":
        h.handleLowStockAlertsSubscription(conn, claims, msg)
    case "subscribe_warehouse_updates":
        h.handleWarehouseUpdatesSubscription(conn, claims, msg)
    case "unsubscribe_inventory":
        h.handleInventoryUnsubscription(conn, claims, msg)
    default:
        h.sendError(conn, "Unknown inventory subscription type: "+msg.Type)
    }
}

func (h *InventoryWebSocketHandler) handleProductUpdatesSubscription(conn *websocket.Conn, claims *auth.Claims, msg ClientMessage) {
    // Check permissions
    if !h.hasPermission(claims, "read:inventory") {
        h.sendError(conn, "Insufficient permissions for product updates")
        return
    }

    var params struct {
        ProductID  string `json:"product_id,omitempty"`
        CategoryID string `json:"category_id,omitempty"`
    }

    if err := json.Unmarshal(msg.Data, &params); err != nil {
        h.sendError(conn, "Invalid subscription parameters")
        return
    }

    // Determine subscription channels
    var channels []string
    
    if params.ProductID != "" {
        // Subscribe to specific product updates
        channels = append(channels, fmt.Sprintf("inventory:product:%s", params.ProductID))
    } else if params.CategoryID != "" {
        // Subscribe to category-wide updates
        channels = append(channels, fmt.Sprintf("inventory:category:%s", params.CategoryID))
    } else {
        // Subscribe to all product updates
        channels = append(channels, "inventory:product_updates")
    }

    // Register subscriptions
    for _, channel := range channels {
        h.baseHandler.connManager.AddSubscription(conn, channel)
        h.baseHandler.redisClient.Subscribe(context.Background(), channel)
    }

    // Send confirmation
    response := map[string]interface{}{
        "type":     "subscription_confirmed",
        "channels": channels,
        "message":  "Successfully subscribed to product updates",
    }
    
    conn.WriteJSON(response)
}

func (h *InventoryWebSocketHandler) handleStockUpdatesSubscription(conn *websocket.Conn, claims *auth.Claims, msg ClientMessage) {
    if !h.hasPermission(claims, "read:inventory") {
        h.sendError(conn, "Insufficient permissions for stock updates")
        return
    }

    var params struct {
        ProductID   string `json:"product_id,omitempty"`
        WarehouseID string `json:"warehouse_id,omitempty"`
        Threshold   int    `json:"threshold,omitempty"` // Only notify if change > threshold
    }

    if err := json.Unmarshal(msg.Data, &params); err != nil {
        h.sendError(conn, "Invalid subscription parameters")
        return
    }

    var channels []string
    
    if params.ProductID != "" && params.WarehouseID != "" {
        // Specific product-warehouse combination
        channels = append(channels, fmt.Sprintf("inventory:stock:%s:%s", params.ProductID, params.WarehouseID))
    } else if params.ProductID != "" {
        // All warehouses for a product
        channels = append(channels, fmt.Sprintf("inventory:product:%s", params.ProductID))
    } else if params.WarehouseID != "" {
        // All products in a warehouse
        channels = append(channels, fmt.Sprintf("inventory:warehouse:%s", params.WarehouseID))
    } else {
        // All stock updates
        channels = append(channels, "inventory:stock_updates")
    }

    // Store subscription metadata for filtering
    subscriptionMeta := map[string]interface{}{
        "type":      "stock_updates",
        "threshold": params.Threshold,
        "user_id":   claims.UserID,
    }

    for _, channel := range channels {
        h.baseHandler.connManager.AddSubscriptionWithMeta(conn, channel, subscriptionMeta)
    }

    response := map[string]interface{}{
        "type":     "subscription_confirmed",
        "channels": channels,
        "message":  "Successfully subscribed to stock updates",
    }
    
    conn.WriteJSON(response)
}

func (h *InventoryWebSocketHandler) handleLowStockAlertsSubscription(conn *websocket.Conn, claims *auth.Claims, msg ClientMessage) {
    if !h.hasPermission(claims, "read:inventory") {
        h.sendError(conn, "Insufficient permissions for low stock alerts")
        return
    }

    var params struct {
        WarehouseIDs []string `json:"warehouse_ids,omitempty"`
        CategoryIDs  []string `json:"category_ids,omitempty"`
        Severity     string   `json:"severity,omitempty"` // "critical", "warning", "all"
    }

    if err := json.Unmarshal(msg.Data, &params); err != nil {
        h.sendError(conn, "Invalid subscription parameters")
        return
    }

    // Subscribe to low stock alerts
    channel := "inventory:low_stock_alerts"
    
    subscriptionMeta := map[string]interface{}{
        "type":          "low_stock_alerts",
        "warehouse_ids": params.WarehouseIDs,
        "category_ids":  params.CategoryIDs,
        "severity":      params.Severity,
        "user_id":       claims.UserID,
    }

    h.baseHandler.connManager.AddSubscriptionWithMeta(conn, channel, subscriptionMeta)

    response := map[string]interface{}{
        "type":    "subscription_confirmed",
        "channel": channel,
        "message": "Successfully subscribed to low stock alerts",
    }
    
    conn.WriteJSON(response)
}
```### 6.
2 Real-time Event Publishing

Create utility functions for publishing real-time inventory events:

```go
// api/ws/inventory_publisher.go
package ws

import (
    "context"
    "encoding/json"
    "fmt"
    "time"

    inventorypb "github.com/your-org/erp-api-gateway/proto/inventory"
)

type InventoryEventPublisher struct {
    redisClient *redis.Client
    logger      *logging.Logger
}

func NewInventoryEventPublisher(redisClient *redis.Client, logger *logging.Logger) *InventoryEventPublisher {
    return &InventoryEventPublisher{
        redisClient: redisClient,
        logger:      logger,
    }
}

// PublishProductCreated publishes a product creation event
func (p *InventoryEventPublisher) PublishProductCreated(ctx context.Context, product *inventorypb.Product, userID string) {
    event := map[string]interface{}{
        "type":       "product_created",
        "product_id": product.Id,
        "product": map[string]interface{}{
            "id":          product.Id,
            "name":        product.Name,
            "sku":         product.Sku,
            "price":       product.Price,
            "category_id": product.CategoryId,
        },
        "user_id":   userID,
        "timestamp": time.Now().UTC(),
        "message":   fmt.Sprintf("New product '%s' has been created", product.Name),
    }

    // Publish to multiple channels
    channels := []string{
        "inventory:product_updates",
        "inventory:notifications",
        fmt.Sprintf("inventory:category:%s", product.CategoryId),
    }

    for _, channel := range channels {
        if err := p.publishEvent(ctx, channel, event); err != nil {
            p.logger.Error("Failed to publish product created event", 
                "channel", channel, "product_id", product.Id, "error", err)
        }
    }
}

// PublishStockUpdated publishes a stock update event
func (p *InventoryEventPublisher) PublishStockUpdated(ctx context.Context, stock *inventorypb.Stock, change int32, userID string) {
    event := map[string]interface{}{
        "type":         "stock_updated",
        "product_id":   stock.ProductId,
        "warehouse_id": stock.WarehouseId,
        "stock": map[string]interface{}{
            "quantity":           stock.Quantity,
            "reserved_quantity":  stock.ReservedQuantity,
            "available_quantity": stock.AvailableQuantity,
        },
        "change":    change,
        "user_id":   userID,
        "timestamp": time.Now().UTC(),
        "message":   fmt.Sprintf("Stock updated for product %s in warehouse %s", stock.ProductId, stock.WarehouseId),
    }

    // Publish to multiple channels for different subscription patterns
    channels := []string{
        "inventory:stock_updates",
        fmt.Sprintf("inventory:product:%s", stock.ProductId),
        fmt.Sprintf("inventory:warehouse:%s", stock.WarehouseId),
        fmt.Sprintf("inventory:stock:%s:%s", stock.ProductId, stock.WarehouseId),
    }

    for _, channel := range channels {
        if err := p.publishEvent(ctx, channel, event); err != nil {
            p.logger.Error("Failed to publish stock updated event", 
                "channel", channel, "product_id", stock.ProductId, "error", err)
        }
    }

    // Check for low stock and publish alert if necessary
    if stock.AvailableQuantity <= 10 { // Configurable threshold
        p.PublishLowStockAlert(ctx, stock, 10)
    }
}

// PublishLowStockAlert publishes a low stock alert
func (p *InventoryEventPublisher) PublishLowStockAlert(ctx context.Context, stock *inventorypb.Stock, threshold int32) {
    severity := "warning"
    if stock.AvailableQuantity <= 5 {
        severity = "critical"
    }

    alert := map[string]interface{}{
        "type":             "low_stock_alert",
        "product_id":       stock.ProductId,
        "warehouse_id":     stock.WarehouseId,
        "current_quantity": stock.AvailableQuantity,
        "threshold":        threshold,
        "severity":         severity,
        "timestamp":        time.Now().UTC(),
        "message":          fmt.Sprintf("Low stock alert: Product %s in warehouse %s has only %d units remaining", 
                                      stock.ProductId, stock.WarehouseId, stock.AvailableQuantity),
    }

    channels := []string{
        "inventory:low_stock_alerts",
        fmt.Sprintf("inventory:warehouse:%s:alerts", stock.WarehouseId),
        "inventory:notifications",
    }

    for _, channel := range channels {
        if err := p.publishEvent(ctx, channel, alert); err != nil {
            p.logger.Error("Failed to publish low stock alert", 
                "channel", channel, "product_id", stock.ProductId, "error", err)
        }
    }
}

// PublishWarehouseUpdated publishes a warehouse update event
func (p *InventoryEventPublisher) PublishWarehouseUpdated(ctx context.Context, warehouse *inventorypb.Warehouse, userID string) {
    event := map[string]interface{}{
        "type":         "warehouse_updated",
        "warehouse_id": warehouse.Id,
        "warehouse": map[string]interface{}{
            "id":         warehouse.Id,
            "name":       warehouse.Name,
            "address":    warehouse.Address,
            "manager_id": warehouse.ManagerId,
            "active":     warehouse.Active,
        },
        "user_id":   userID,
        "timestamp": time.Now().UTC(),
        "message":   fmt.Sprintf("Warehouse '%s' has been updated", warehouse.Name),
    }

    channels := []string{
        "inventory:warehouse_updates",
        fmt.Sprintf("inventory:warehouse:%s", warehouse.Id),
        "inventory:notifications",
    }

    for _, channel := range channels {
        if err := p.publishEvent(ctx, channel, event); err != nil {
            p.logger.Error("Failed to publish warehouse updated event", 
                "channel", channel, "warehouse_id", warehouse.Id, "error", err)
        }
    }
}

func (p *InventoryEventPublisher) publishEvent(ctx context.Context, channel string, event map[string]interface{}) error {
    data, err := json.Marshal(event)
    if err != nil {
        return fmt.Errorf("failed to marshal event: %w", err)
    }

    return p.redisClient.Publish(ctx, channel, string(data))
}
```### 6.3 
WebSocket Client Usage Examples

Here are examples of how clients can subscribe to inventory real-time updates:

```javascript
// JavaScript WebSocket client example
const ws = new WebSocket('wss://api.erp-system.com/ws', [], {
  headers: {
    'Authorization': 'Bearer ' + accessToken
  }
});

ws.onopen = function() {
  console.log('WebSocket connected');
  
  // Subscribe to all product updates
  ws.send(JSON.stringify({
    type: 'subscribe_product_updates',
    data: {}
  }));
  
  // Subscribe to stock updates for specific product
  ws.send(JSON.stringify({
    type: 'subscribe_stock_updates',
    data: {
      product_id: 'product-123',
      threshold: 5 // Only notify if change > 5 units
    }
  }));
  
  // Subscribe to low stock alerts for specific warehouses
  ws.send(JSON.stringify({
    type: 'subscribe_low_stock_alerts',
    data: {
      warehouse_ids: ['warehouse-1', 'warehouse-2'],
      severity: 'critical'
    }
  }));
};

ws.onmessage = function(event) {
  const message = JSON.parse(event.data);
  
  switch(message.type) {
    case 'product_created':
      console.log('New product created:', message.product);
      updateProductList(message.product);
      showNotification(`New product "${message.product.name}" created`);
      break;
      
    case 'stock_updated':
      console.log('Stock updated:', message);
      updateStockDisplay(message.product_id, message.stock);
      if (Math.abs(message.change) > 10) {
        showNotification(`Stock changed by ${message.change} units`);
      }
      break;
      
    case 'low_stock_alert':
      console.log('Low stock alert:', message);
      showLowStockAlert(message);
      break;
      
    case 'subscription_confirmed':
      console.log('Subscription confirmed:', message.channels);
      break;
      
    default:
      console.log('Unknown message type:', message.type);
  }
};

// React component example
function InventoryDashboard() {
  const [products, setProducts] = useState([]);
  const [stockAlerts, setStockAlerts] = useState([]);
  const [ws, setWs] = useState(null);

  useEffect(() => {
    const websocket = new WebSocket('wss://api.erp-system.com/ws', [], {
      headers: { 'Authorization': `Bearer ${getAccessToken()}` }
    });

    websocket.onopen = () => {
      // Subscribe to inventory notifications
      websocket.send(JSON.stringify({
        type: 'subscribe_product_updates',
        data: {}
      }));
      
      websocket.send(JSON.stringify({
        type: 'subscribe_low_stock_alerts',
        data: { severity: 'all' }
      }));
    };

    websocket.onmessage = (event) => {
      const message = JSON.parse(event.data);
      
      switch(message.type) {
        case 'product_created':
          setProducts(prev => [...prev, message.product]);
          toast.success(`New product "${message.product.name}" created`);
          break;
          
        case 'low_stock_alert':
          setStockAlerts(prev => [...prev, message]);
          if (message.severity === 'critical') {
            toast.error(`Critical: Low stock for product ${message.product_id}`);
          }
          break;
      }
    };

    setWs(websocket);

    return () => {
      websocket.close();
    };
  }, []);

  return (
    <div>
      <ProductList products={products} />
      <StockAlerts alerts={stockAlerts} />
    </div>
  );
}
```## Ste
p 7: Authentication & Authorization

### 7.1 Define Permissions

Add inventory-specific permissions to the RBAC system:

```go
// middleware/rbac.go - Update permission definitions
var InventoryPermissions = map[string]string{
    "read:inventory":      "Read inventory data (products, stock, warehouses)",
    "write:inventory":     "Create and update inventory items",
    "delete:inventory":    "Delete inventory items",
    "manage:warehouses":   "Full warehouse management access",
    "manage:stock":        "Stock level management and adjustments",
    "view:reports":        "Access to inventory reports and analytics",
    "manage:categories":   "Product category management",
    "bulk:operations":     "Bulk inventory operations",
}

// Update role definitions
var DefaultRoles = map[string][]string{
    "inventory_viewer": {
        "read:inventory",
        "view:reports",
    },
    "inventory_manager": {
        "read:inventory",
        "write:inventory",
        "manage:stock",
        "view:reports",
        "manage:categories",
    },
    "warehouse_manager": {
        "read:inventory",
        "write:inventory",
        "manage:stock",
        "manage:warehouses",
        "view:reports",
        "bulk:operations",
    },
    "inventory_admin": {
        "read:inventory",
        "write:inventory",
        "delete:inventory",
        "manage:warehouses",
        "manage:stock",
        "view:reports",
        "manage:categories",
        "bulk:operations",
    },
}
```

### 7.2 Implement Permission Checks

Add permission validation to handlers:

```go
// api/rest/inventory_handler.go - Add permission helpers
func (h *InventoryHandler) checkInventoryPermission(c *gin.Context, permission string) bool {
    userClaims := getUserClaims(c)
    if userClaims == nil {
        return false
    }

    // Check direct permissions
    for _, userPerm := range userClaims.Permissions {
        if userPerm == permission {
            return true
        }
    }

    // Check role-based permissions
    for _, role := range userClaims.Roles {
        if rolePerms, exists := DefaultRoles[role]; exists {
            for _, rolePerm := range rolePerms {
                if rolePerm == permission {
                    return true
                }
            }
        }
    }

    return false
}

// Enhanced permission checking with context
func (h *InventoryHandler) checkResourcePermission(c *gin.Context, permission string, resourceID string) bool {
    if !h.checkInventoryPermission(c, permission) {
        return false
    }

    userClaims := getUserClaims(c)
    
    // Additional context-based checks
    switch permission {
    case "manage:warehouses":
        // Check if user is manager of this warehouse
        return h.isWarehouseManager(c.Request.Context(), userClaims.UserID, resourceID)
    case "manage:stock":
        // Check if user has access to this product's warehouse
        return h.hasWarehouseAccess(c.Request.Context(), userClaims.UserID, resourceID)
    }

    return true
}

func (h *InventoryHandler) isWarehouseManager(ctx context.Context, userID, warehouseID string) bool {
    // Check if user is assigned as manager of the warehouse
    client := h.grpcClient.InventoryService()
    resp, err := client.GetWarehouse(ctx, &inventorypb.GetWarehouseRequest{
        WarehouseId: warehouseID,
    })

    if err != nil || !resp.Success {
        return false
    }

    return resp.Data.ManagerId == userID
}
```

### 7.3 Middleware Integration

Update route registration with proper permission checks:

```go
// internal/server/server.go - Enhanced route setup
func (s *Server) setupInventoryRoutes() {
    inventoryGroup := s.router.Group("/api/v1/inventory")
    inventoryGroup.Use(middleware.RequireAuth(s.container.AuthValidator))
    
    inventoryHandler := rest.NewInventoryHandler(s.container)

    // Product routes with granular permissions
    productGroup := inventoryGroup.Group("/products")
    {
        // Read operations
        readGroup := productGroup.Group("")
        readGroup.Use(middleware.RequirePermission("read:inventory"))
        {
            readGroup.GET("/", inventoryHandler.GetProducts)
            readGroup.GET("/:id", inventoryHandler.GetProduct)
            readGroup.GET("/:id/stock", inventoryHandler.GetProductStock)
        }

        // Write operations
        writeGroup := productGroup.Group("")
        writeGroup.Use(middleware.RequirePermission("write:inventory"))
        {
            writeGroup.POST("/", inventoryHandler.CreateProduct)
            writeGroup.PUT("/:id", inventoryHandler.UpdateProduct)
        }

        // Delete operations (higher permission required)
        deleteGroup := productGroup.Group("")
        deleteGroup.Use(middleware.RequirePermission("delete:inventory"))
        {
            deleteGroup.DELETE("/:id", inventoryHandler.DeleteProduct)
        }

        // Bulk operations
        bulkGroup := productGroup.Group("/bulk")
        bulkGroup.Use(middleware.RequirePermission("bulk:operations"))
        {
            bulkGroup.POST("/create", inventoryHandler.BulkCreateProducts)
            bulkGroup.PUT("/update", inventoryHandler.BulkUpdateProducts)
            bulkGroup.DELETE("/delete", inventoryHandler.BulkDeleteProducts)
        }
    }

    // Stock management routes
    stockGroup := inventoryGroup.Group("/stock")
    stockGroup.Use(middleware.RequirePermission("read:inventory"))
    {
        stockGroup.GET("/", inventoryHandler.GetStock)
        stockGroup.GET("/history", inventoryHandler.GetStockHistory)
        stockGroup.GET("/low-stock", inventoryHandler.GetLowStockItems)

        // Stock modifications
        manageGroup := stockGroup.Group("")
        manageGroup.Use(middleware.RequirePermission("manage:stock"))
        {
            manageGroup.PUT("/adjust", inventoryHandler.AdjustStock)
            manageGroup.POST("/transfer", inventoryHandler.TransferStock)
            manageGroup.POST("/reserve", inventoryHandler.ReserveStock)
            manageGroup.POST("/release", inventoryHandler.ReleaseStock)
        }
    }

    // Warehouse routes (restricted access)
    warehouseGroup := inventoryGroup.Group("/warehouses")
    warehouseGroup.Use(middleware.RequirePermission("manage:warehouses"))
    {
        warehouseGroup.GET("/", inventoryHandler.GetWarehouses)
        warehouseGroup.GET("/:id", inventoryHandler.GetWarehouse)
        warehouseGroup.POST("/", inventoryHandler.CreateWarehouse)
        warehouseGroup.PUT("/:id", inventoryHandler.UpdateWarehouse)
        warehouseGroup.DELETE("/:id", inventoryHandler.DeleteWarehouse)
        
        // Warehouse-specific stock operations
        warehouseGroup.GET("/:id/stock", inventoryHandler.GetWarehouseStock)
        warehouseGroup.GET("/:id/capacity", inventoryHandler.GetWarehouseCapacity)
    }

    // Reports (read-only, special permission)
    reportsGroup := inventoryGroup.Group("/reports")
    reportsGroup.Use(middleware.RequirePermission("view:reports"))
    {
        reportsGroup.GET("/stock-levels", inventoryHandler.GetStockLevelsReport)
        reportsGroup.GET("/low-stock", inventoryHandler.GetLowStockReport)
        reportsGroup.GET("/stock-movements", inventoryHandler.GetStockMovementsReport)
        reportsGroup.GET("/warehouse-utilization", inventoryHandler.GetWarehouseUtilizationReport)
    }
}
```## Step 8
: Caching Strategy

### 8.1 Implement Caching Layer

Create a comprehensive caching strategy for inventory data:

```go
// internal/services/cache/inventory_cache.go
package cache

import (
    "context"
    "encoding/json"
    "fmt"
    "time"

    inventorypb "github.com/your-org/erp-api-gateway/proto/inventory"
    "github.com/your-org/erp-api-gateway/internal/services/redis"
)

type InventoryCache struct {
    redisClient *redis.Client
    logger      *logging.Logger
}

func NewInventoryCache(redisClient *redis.Client, logger *logging.Logger) *InventoryCache {
    return &InventoryCache{
        redisClient: redisClient,
        logger:      logger,
    }
}

// Product caching
func (c *InventoryCache) GetProduct(ctx context.Context, productID string) (*inventorypb.Product, error) {
    key := fmt.Sprintf("inventory:product:%s", productID)
    
    data, err := c.redisClient.Get(ctx, key)
    if err != nil {
        return nil, err
    }

    var product inventorypb.Product
    if err := json.Unmarshal(data, &product); err != nil {
        return nil, err
    }

    return &product, nil
}

func (c *InventoryCache) SetProduct(ctx context.Context, product *inventorypb.Product, ttl time.Duration) error {
    key := fmt.Sprintf("inventory:product:%s", product.Id)
    
    data, err := json.Marshal(product)
    if err != nil {
        return err
    }

    return c.redisClient.Set(ctx, key, data, ttl)
}

func (c *InventoryCache) InvalidateProduct(ctx context.Context, productID string) error {
    keys := []string{
        fmt.Sprintf("inventory:product:%s", productID),
        fmt.Sprintf("inventory:product:%s:stock", productID),
    }

    // Also invalidate related list caches
    listKeys := []string{
        "inventory:products:*",
        "inventory:search:*",
    }

    for _, pattern := range listKeys {
        if matchingKeys, err := c.redisClient.Keys(ctx, pattern); err == nil {
            keys = append(keys, matchingKeys...)
        }
    }

    return c.redisClient.DeleteMultiple(ctx, keys)
}

// Stock caching with shorter TTL (more volatile data)
func (c *InventoryCache) GetStock(ctx context.Context, productID, warehouseID string) (*inventorypb.Stock, error) {
    key := fmt.Sprintf("inventory:stock:%s:%s", productID, warehouseID)
    
    data, err := c.redisClient.Get(ctx, key)
    if err != nil {
        return nil, err
    }

    var stock inventorypb.Stock
    if err := json.Unmarshal(data, &stock); err != nil {
        return nil, err
    }

    return &stock, nil
}

func (c *InventoryCache) SetStock(ctx context.Context, stock *inventorypb.Stock) error {
    key := fmt.Sprintf("inventory:stock:%s:%s", stock.ProductId, stock.WarehouseId)
    
    data, err := json.Marshal(stock)
    if err != nil {
        return err
    }

    // Stock data has shorter TTL (1 minute) due to frequent updates
    return c.redisClient.Set(ctx, key, data, time.Minute)
}

func (c *InventoryCache) InvalidateStock(ctx context.Context, productID, warehouseID string) error {
    keys := []string{
        fmt.Sprintf("inventory:stock:%s:%s", productID, warehouseID),
        fmt.Sprintf("inventory:product:%s:stock", productID),
        fmt.Sprintf("inventory:warehouse:%s:stock", warehouseID),
    }

    return c.redisClient.DeleteMultiple(ctx, keys)
}

// Product list caching with pagination
func (c *InventoryCache) GetProductList(ctx context.Context, params ProductListParams) (*ProductListResult, error) {
    key := c.buildProductListKey(params)
    
    data, err := c.redisClient.Get(ctx, key)
    if err != nil {
        return nil, err
    }

    var result ProductListResult
    if err := json.Unmarshal(data, &result); err != nil {
        return nil, err
    }

    return &result, nil
}

func (c *InventoryCache) SetProductList(ctx context.Context, params ProductListParams, result *ProductListResult) error {
    key := c.buildProductListKey(params)
    
    data, err := json.Marshal(result)
    if err != nil {
        return err
    }

    // Product lists cached for 5 minutes
    return c.redisClient.Set(ctx, key, data, 5*time.Minute)
}

func (c *InventoryCache) buildProductListKey(params ProductListParams) string {
    return fmt.Sprintf("inventory:products:page:%d:limit:%d:search:%s:category:%s:sort:%s:%s",
        params.Page, params.Limit, params.Search, params.CategoryID, params.SortBy, params.SortOrder)
}

// Warehouse caching (relatively stable data)
func (c *InventoryCache) GetWarehouse(ctx context.Context, warehouseID string) (*inventorypb.Warehouse, error) {
    key := fmt.Sprintf("inventory:warehouse:%s", warehouseID)
    
    data, err := c.redisClient.Get(ctx, key)
    if err != nil {
        return nil, err
    }

    var warehouse inventorypb.Warehouse
    if err := json.Unmarshal(data, &warehouse); err != nil {
        return nil, err
    }

    return &warehouse, nil
}

func (c *InventoryCache) SetWarehouse(ctx context.Context, warehouse *inventorypb.Warehouse) error {
    key := fmt.Sprintf("inventory:warehouse:%s", warehouse.Id)
    
    data, err := json.Marshal(warehouse)
    if err != nil {
        return err
    }

    // Warehouses cached for 1 hour (stable data)
    return c.redisClient.Set(ctx, key, data, time.Hour)
}

// Cache warming strategies
func (c *InventoryCache) WarmProductCache(ctx context.Context, productIDs []string) error {
    // This would typically be called during off-peak hours
    // or when we know certain products will be accessed frequently
    
    for _, productID := range productIDs {
        // Check if already cached
        if _, err := c.GetProduct(ctx, productID); err == nil {
            continue // Already cached
        }

        // Fetch from service and cache
        // This would require access to the gRPC client
        // Implementation depends on your specific architecture
    }

    return nil
}

// Cache statistics and monitoring
func (c *InventoryCache) GetCacheStats(ctx context.Context) (*CacheStats, error) {
    stats := &CacheStats{}

    // Count different types of cached items
    patterns := map[string]string{
        "products":   "inventory:product:*",
        "stock":      "inventory:stock:*",
        "warehouses": "inventory:warehouse:*",
        "lists":      "inventory:products:*",
    }

    for category, pattern := range patterns {
        if keys, err := c.redisClient.Keys(ctx, pattern); err == nil {
            stats.ItemCounts[category] = len(keys)
        }
    }

    return stats, nil
}

type ProductListParams struct {
    Page       int
    Limit      int
    Search     string
    CategoryID string
    SortBy     string
    SortOrder  string
}

type ProductListResult struct {
    Products   []*inventorypb.Product `json:"products"`
    TotalCount int                    `json:"total_count"`
    Page       int                    `json:"page"`
    Limit      int                    `json:"limit"`
}

type CacheStats struct {
    ItemCounts map[string]int `json:"item_counts"`
    HitRate    float64        `json:"hit_rate"`
    MissRate   float64        `json:"miss_rate"`
}
```### 
8.2 Cache Integration in Handlers

Update handlers to use the caching layer:

```go
// api/rest/inventory_handler.go - Enhanced with caching
func (h *InventoryHandler) GetProduct(c *gin.Context) {
    productID := c.Param("id")
    
    // Try cache first
    if product, err := h.cache.GetProduct(c.Request.Context(), productID); err == nil {
        response := h.convertProductToREST(product)
        c.Header("X-Cache", "HIT")
        c.JSON(200, gin.H{
            "success": true,
            "data":    response,
            "message": "Product retrieved successfully",
        })
        return
    }

    // Cache miss - fetch from service
    client := h.grpcClient.InventoryService()
    resp, err := client.GetProduct(c.Request.Context(), &inventorypb.GetProductRequest{
        ProductId: productID,
    })

    if err != nil {
        h.logger.Error("Failed to get product", "error", err, "product_id", productID)
        c.JSON(500, gin.H{
            "success": false,
            "message": "Failed to retrieve product",
        })
        return
    }

    if !resp.Success {
        c.JSON(404, gin.H{
            "success": false,
            "message": resp.Message,
        })
        return
    }

    // Cache the result
    h.cache.SetProduct(c.Request.Context(), resp.Data, 10*time.Minute)

    response := h.convertProductToREST(resp.Data)
    c.Header("X-Cache", "MISS")
    c.JSON(200, gin.H{
        "success": true,
        "data":    response,
        "message": "Product retrieved successfully",
    })
}

func (h *InventoryHandler) UpdateProduct(c *gin.Context) {
    productID := c.Param("id")
    
    var req UpdateProductRequest
    if err := c.ShouldBindJSON(&req); err != nil {
        c.JSON(400, gin.H{
            "success": false,
            "message": "Invalid request data",
            "errors":  parseValidationErrors(err),
        })
        return
    }

    userClaims := getUserClaims(c)

    // Make gRPC call
    client := h.grpcClient.InventoryService()
    resp, err := client.UpdateProduct(c.Request.Context(), &inventorypb.UpdateProductRequest{
        ProductId:   productID,
        Name:        req.Name,
        Description: req.Description,
        Price:       req.Price,
        CategoryId:  req.CategoryID,
    })

    if err != nil {
        h.logger.Error("Failed to update product", "error", err, "product_id", productID)
        c.JSON(500, gin.H{
            "success": false,
            "message": "Failed to update product",
        })
        return
    }

    if resp.Success {
        // Invalidate cache
        h.cache.InvalidateProduct(c.Request.Context(), productID)
        
        // Cache the updated product
        h.cache.SetProduct(c.Request.Context(), resp.Data, 10*time.Minute)
        
        // Publish real-time update
        h.publishProductUpdated(c.Request.Context(), resp.Data, userClaims.UserID)
        
        // Publish business event
        h.kafkaProducer.PublishEvent(c.Request.Context(), "inventory.product.updated", map[string]interface{}{
            "product_id": productID,
            "user_id":    userClaims.UserID,
            "timestamp":  time.Now().UTC(),
            "changes":    req,
        })
    }

    response := h.convertUpdateProductResponse(resp)
    c.JSON(200, response)
}

// Cache-aware stock operations
func (h *InventoryHandler) GetStock(c *gin.Context) {
    productID := c.Query("product_id")
    warehouseID := c.Query("warehouse_id")

    if productID == "" || warehouseID == "" {
        c.JSON(400, gin.H{
            "success": false,
            "message": "product_id and warehouse_id are required",
        })
        return
    }

    // Try cache first (stock has shorter TTL)
    if stock, err := h.cache.GetStock(c.Request.Context(), productID, warehouseID); err == nil {
        response := h.convertStockToREST(stock)
        c.Header("X-Cache", "HIT")
        c.JSON(200, gin.H{
            "success": true,
            "data":    response,
        })
        return
    }

    // Fetch from service
    client := h.grpcClient.InventoryService()
    resp, err := client.GetStock(c.Request.Context(), &inventorypb.GetStockRequest{
        ProductId:   productID,
        WarehouseId: warehouseID,
    })

    if err != nil {
        h.logger.Error("Failed to get stock", "error", err)
        c.JSON(500, gin.H{
            "success": false,
            "message": "Failed to retrieve stock",
        })
        return
    }

    if resp.Success {
        // Cache stock data (shorter TTL due to frequent updates)
        h.cache.SetStock(c.Request.Context(), resp.Data)
    }

    response := h.convertGetStockResponse(resp)
    c.Header("X-Cache", "MISS")
    c.JSON(200, response)
}
```## Step
 9: Event Publishing

### 9.1 Kafka Event Publishing

Create comprehensive event publishing for inventory operations:

```go
// internal/services/kafka/inventory_events.go
package kafka

import (
    "context"
    "encoding/json"
    "fmt"
    "time"

    inventorypb "github.com/your-org/erp-api-gateway/proto/inventory"
)

type InventoryEventPublisher struct {
    producer *Producer
    logger   *logging.Logger
}

func NewInventoryEventPublisher(producer *Producer, logger *logging.Logger) *InventoryEventPublisher {
    return &InventoryEventPublisher{
        producer: producer,
        logger:   logger,
    }
}

// Product events
func (p *InventoryEventPublisher) PublishProductCreated(ctx context.Context, product *inventorypb.Product, userID string) error {
    event := InventoryEvent{
        EventType:     "ProductCreated",
        EventVersion:  "1.0",
        EventID:       generateEventID(),
        Timestamp:     time.Now().UTC(),
        UserID:        userID,
        AggregateID:   product.Id,
        AggregateType: "Product",
        Data: ProductCreatedData{
            Product: ProductData{
                ID:          product.Id,
                Name:        product.Name,
                Description: product.Description,
                SKU:         product.Sku,
                Price:       product.Price,
                CategoryID:  product.CategoryId,
                CreatedAt:   product.CreatedAt.AsTime(),
            },
            CreatedBy: userID,
        },
        Metadata: EventMetadata{
            Source:        "api-gateway",
            CorrelationID: getCorrelationID(ctx),
            CausationID:   getCausationID(ctx),
        },
    }

    return p.publishEvent(ctx, "inventory.product.created", event)
}

func (p *InventoryEventPublisher) PublishProductUpdated(ctx context.Context, product *inventorypb.Product, userID string, changes map[string]interface{}) error {
    event := InventoryEvent{
        EventType:     "ProductUpdated",
        EventVersion:  "1.0",
        EventID:       generateEventID(),
        Timestamp:     time.Now().UTC(),
        UserID:        userID,
        AggregateID:   product.Id,
        AggregateType: "Product",
        Data: ProductUpdatedData{
            ProductID: product.Id,
            Changes:   changes,
            UpdatedBy: userID,
            UpdatedAt: time.Now().UTC(),
        },
        Metadata: EventMetadata{
            Source:        "api-gateway",
            CorrelationID: getCorrelationID(ctx),
            CausationID:   getCausationID(ctx),
        },
    }

    return p.publishEvent(ctx, "inventory.product.updated", event)
}

func (p *InventoryEventPublisher) PublishProductDeleted(ctx context.Context, productID, userID string) error {
    event := InventoryEvent{
        EventType:     "ProductDeleted",
        EventVersion:  "1.0",
        EventID:       generateEventID(),
        Timestamp:     time.Now().UTC(),
        UserID:        userID,
        AggregateID:   productID,
        AggregateType: "Product",
        Data: ProductDeletedData{
            ProductID: productID,
            DeletedBy: userID,
            DeletedAt: time.Now().UTC(),
        },
        Metadata: EventMetadata{
            Source:        "api-gateway",
            CorrelationID: getCorrelationID(ctx),
        },
    }

    return p.publishEvent(ctx, "inventory.product.deleted", event)
}

// Stock events
func (p *InventoryEventPublisher) PublishStockUpdated(ctx context.Context, stock *inventorypb.Stock, change int32, reason, userID string) error {
    event := InventoryEvent{
        EventType:     "StockUpdated",
        EventVersion:  "1.0",
        EventID:       generateEventID(),
        Timestamp:     time.Now().UTC(),
        UserID:        userID,
        AggregateID:   fmt.Sprintf("%s:%s", stock.ProductId, stock.WarehouseId),
        AggregateType: "Stock",
        Data: StockUpdatedData{
            ProductID:         stock.ProductId,
            WarehouseID:       stock.WarehouseId,
            PreviousQuantity:  stock.Quantity - change,
            NewQuantity:       stock.Quantity,
            Change:            change,
            Reason:            reason,
            UpdatedBy:         userID,
            AvailableQuantity: stock.AvailableQuantity,
            ReservedQuantity:  stock.ReservedQuantity,
        },
        Metadata: EventMetadata{
            Source:        "api-gateway",
            CorrelationID: getCorrelationID(ctx),
        },
    }

    return p.publishEvent(ctx, "inventory.stock.updated", event)
}

func (p *InventoryEventPublisher) PublishLowStockAlert(ctx context.Context, productID, warehouseID string, currentQuantity, threshold int32) error {
    severity := "warning"
    if currentQuantity <= threshold/2 {
        severity = "critical"
    }

    event := InventoryEvent{
        EventType:     "LowStockAlert",
        EventVersion:  "1.0",
        EventID:       generateEventID(),
        Timestamp:     time.Now().UTC(),
        AggregateID:   fmt.Sprintf("%s:%s", productID, warehouseID),
        AggregateType: "Stock",
        Data: LowStockAlertData{
            ProductID:       productID,
            WarehouseID:     warehouseID,
            CurrentQuantity: currentQuantity,
            Threshold:       threshold,
            Severity:        severity,
            AlertedAt:       time.Now().UTC(),
        },
        Metadata: EventMetadata{
            Source:        "api-gateway",
            CorrelationID: getCorrelationID(ctx),
        },
    }

    return p.publishEvent(ctx, "inventory.stock.low_stock_alert", event)
}

// Warehouse events
func (p *InventoryEventPublisher) PublishWarehouseCreated(ctx context.Context, warehouse *inventorypb.Warehouse, userID string) error {
    event := InventoryEvent{
        EventType:     "WarehouseCreated",
        EventVersion:  "1.0",
        EventID:       generateEventID(),
        Timestamp:     time.Now().UTC(),
        UserID:        userID,
        AggregateID:   warehouse.Id,
        AggregateType: "Warehouse",
        Data: WarehouseCreatedData{
            Warehouse: WarehouseData{
                ID:        warehouse.Id,
                Name:      warehouse.Name,
                Address:   warehouse.Address,
                ManagerID: warehouse.ManagerId,
                Active:    warehouse.Active,
                CreatedAt: warehouse.CreatedAt.AsTime(),
            },
            CreatedBy: userID,
        },
        Metadata: EventMetadata{
            Source:        "api-gateway",
            CorrelationID: getCorrelationID(ctx),
        },
    }

    return p.publishEvent(ctx, "inventory.warehouse.created", event)
}

func (p *InventoryEventPublisher) publishEvent(ctx context.Context, topic string, event InventoryEvent) error {
    eventData, err := json.Marshal(event)
    if err != nil {
        return fmt.Errorf("failed to marshal event: %w", err)
    }

    // Add event to producer with retry logic
    if err := p.producer.PublishEvent(ctx, topic, eventData); err != nil {
        p.logger.Error("Failed to publish inventory event", 
            "topic", topic, 
            "event_type", event.EventType, 
            "event_id", event.EventID, 
            "error", err)
        return err
    }

    p.logger.Info("Published inventory event", 
        "topic", topic, 
        "event_type", event.EventType, 
        "event_id", event.EventID,
        "aggregate_id", event.AggregateID)

    return nil
}

// Event data structures
type InventoryEvent struct {
    EventType     string        `json:"event_type"`
    EventVersion  string        `json:"event_version"`
    EventID       string        `json:"event_id"`
    Timestamp     time.Time     `json:"timestamp"`
    UserID        string        `json:"user_id,omitempty"`
    AggregateID   string        `json:"aggregate_id"`
    AggregateType string        `json:"aggregate_type"`
    Data          interface{}   `json:"data"`
    Metadata      EventMetadata `json:"metadata"`
}

type EventMetadata struct {
    Source        string `json:"source"`
    CorrelationID string `json:"correlation_id,omitempty"`
    CausationID   string `json:"causation_id,omitempty"`
}

type ProductData struct {
    ID          string    `json:"id"`
    Name        string    `json:"name"`
    Description string    `json:"description"`
    SKU         string    `json:"sku"`
    Price       float64   `json:"price"`
    CategoryID  string    `json:"category_id"`
    CreatedAt   time.Time `json:"created_at"`
}

type ProductCreatedData struct {
    Product   ProductData `json:"product"`
    CreatedBy string      `json:"created_by"`
}

type ProductUpdatedData struct {
    ProductID string                 `json:"product_id"`
    Changes   map[string]interface{} `json:"changes"`
    UpdatedBy string                 `json:"updated_by"`
    UpdatedAt time.Time              `json:"updated_at"`
}

type ProductDeletedData struct {
    ProductID string    `json:"product_id"`
    DeletedBy string    `json:"deleted_by"`
    DeletedAt time.Time `json:"deleted_at"`
}

type StockUpdatedData struct {
    ProductID         string `json:"product_id"`
    WarehouseID       string `json:"warehouse_id"`
    PreviousQuantity  int32  `json:"previous_quantity"`
    NewQuantity       int32  `json:"new_quantity"`
    Change            int32  `json:"change"`
    Reason            string `json:"reason"`
    UpdatedBy         string `json:"updated_by"`
    AvailableQuantity int32  `json:"available_quantity"`
    ReservedQuantity  int32  `json:"reserved_quantity"`
}

type LowStockAlertData struct {
    ProductID       string    `json:"product_id"`
    WarehouseID     string    `json:"warehouse_id"`
    CurrentQuantity int32     `json:"current_quantity"`
    Threshold       int32     `json:"threshold"`
    Severity        string    `json:"severity"`
    AlertedAt       time.Time `json:"alerted_at"`
}

type WarehouseData struct {
    ID        string    `json:"id"`
    Name      string    `json:"name"`
    Address   string    `json:"address"`
    ManagerID string    `json:"manager_id"`
    Active    bool      `json:"active"`
    CreatedAt time.Time `json:"created_at"`
}

type WarehouseCreatedData struct {
    Warehouse WarehouseData `json:"warehouse"`
    CreatedBy string        `json:"created_by"`
}
```## St
ep 10: Testing Integration

### 10.1 Unit Tests

Create comprehensive unit tests for the inventory integration:

```go
// api/rest/inventory_handler_test.go
package rest

import (
    "bytes"
    "context"
    "encoding/json"
    "net/http"
    "net/http/httptest"
    "testing"
    "time"

    "github.com/gin-gonic/gin"
    "github.com/stretchr/testify/assert"
    "github.com/stretchr/testify/mock"
    "github.com/stretchr/testify/require"

    inventorypb "github.com/your-org/erp-api-gateway/proto/inventory"
    "github.com/your-org/erp-api-gateway/test/mocks"
)

func TestInventoryHandler_GetProducts(t *testing.T) {
    tests := []struct {
        name           string
        queryParams    string
        mockSetup      func(*mocks.MockGRPCClient, *mocks.MockRedisClient)
        expectedStatus int
        expectedData   interface{}
    }{
        {
            name:        "successful get products",
            queryParams: "?page=1&limit=10",
            mockSetup: func(grpc *mocks.MockGRPCClient, redis *mocks.MockRedisClient) {
                // Mock cache miss
                redis.On("Get", mock.Anything, mock.AnythingOfType("string")).Return(nil, errors.New("cache miss"))

                // Mock gRPC response
                grpc.On("InventoryService").Return(&mocks.MockInventoryServiceClient{})
                grpc.InventoryService().(*mocks.MockInventoryServiceClient).On("GetProducts", 
                    mock.Anything, 
                    mock.MatchedBy(func(req *inventorypb.GetProductsRequest) bool {
                        return req.Page == 1 && req.Limit == 10
                    })).Return(&inventorypb.GetProductsResponse{
                    Success: true,
                    Data: []*inventorypb.Product{
                        {
                            Id:          "product-1",
                            Name:        "Test Product",
                            Sku:         "TEST-001",
                            Price:       99.99,
                            CategoryId:  "category-1",
                        },
                    },
                    Meta: &commonpb.PaginationMeta{
                        CurrentPage: 1,
                        PerPage:     10,
                        Total:       1,
                        LastPage:    1,
                    },
                }, nil)

                // Mock cache set
                redis.On("Set", mock.Anything, mock.AnythingOfType("string"), mock.Anything, mock.AnythingOfType("time.Duration")).Return(nil)
            },
            expectedStatus: 200,
        },
        {
            name:        "grpc service error",
            queryParams: "?page=1&limit=10",
            mockSetup: func(grpc *mocks.MockGRPCClient, redis *mocks.MockRedisClient) {
                redis.On("Get", mock.Anything, mock.AnythingOfType("string")).Return(nil, errors.New("cache miss"))
                grpc.On("InventoryService").Return(&mocks.MockInventoryServiceClient{})
                grpc.InventoryService().(*mocks.MockInventoryServiceClient).On("GetProducts", 
                    mock.Anything, mock.Anything).Return(nil, errors.New("service unavailable"))
            },
            expectedStatus: 500,
        },
        {
            name:        "cache hit",
            queryParams: "?page=1&limit=10",
            mockSetup: func(grpc *mocks.MockGRPCClient, redis *mocks.MockRedisClient) {
                cachedResponse := map[string]interface{}{
                    "success": true,
                    "data": []map[string]interface{}{
                        {
                            "id":   "product-1",
                            "name": "Cached Product",
                            "sku":  "CACHE-001",
                        },
                    },
                }
                cachedData, _ := json.Marshal(cachedResponse)
                redis.On("Get", mock.Anything, mock.AnythingOfType("string")).Return(cachedData, nil)
            },
            expectedStatus: 200,
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            // Setup mocks
            mockGRPC := &mocks.MockGRPCClient{}
            mockRedis := &mocks.MockRedisClient{}
            mockKafka := &mocks.MockKafkaProducer{}
            mockLogger := &mocks.MockLogger{}

            tt.mockSetup(mockGRPC, mockRedis)

            // Create handler
            handler := &InventoryHandler{
                grpcClient:    mockGRPC,
                redisClient:   mockRedis,
                kafkaProducer: mockKafka,
                logger:        mockLogger,
            }

            // Setup Gin
            gin.SetMode(gin.TestMode)
            router := gin.New()
            router.GET("/products", handler.GetProducts)

            // Create request
            req := httptest.NewRequest("GET", "/products"+tt.queryParams, nil)
            w := httptest.NewRecorder()

            // Execute request
            router.ServeHTTP(w, req)

            // Assert response
            assert.Equal(t, tt.expectedStatus, w.Code)

            if tt.expectedStatus == 200 {
                var response map[string]interface{}
                err := json.Unmarshal(w.Body.Bytes(), &response)
                require.NoError(t, err)
                assert.True(t, response["success"].(bool))
            }

            // Verify mocks
            mockGRPC.AssertExpectations(t)
            mockRedis.AssertExpectations(t)
        })
    }
}

func TestInventoryHandler_CreateProduct(t *testing.T) {
    tests := []struct {
        name           string
        requestBody    CreateProductRequest
        userClaims     *auth.Claims
        mockSetup      func(*mocks.MockGRPCClient, *mocks.MockKafkaProducer, *mocks.MockRedisClient)
        expectedStatus int
    }{
        {
            name: "successful product creation",
            requestBody: CreateProductRequest{
                Name:        "New Product",
                Description: "Product description",
                SKU:         "NEW-001",
                Price:       149.99,
                CategoryID:  "category-1",
            },
            userClaims: &auth.Claims{
                UserID:      "user-123",
                Permissions: []string{"write:inventory"},
            },
            mockSetup: func(grpc *mocks.MockGRPCClient, kafka *mocks.MockKafkaProducer, redis *mocks.MockRedisClient) {
                grpc.On("InventoryService").Return(&mocks.MockInventoryServiceClient{})
                grpc.InventoryService().(*mocks.MockInventoryServiceClient).On("CreateProduct",
                    mock.Anything,
                    mock.MatchedBy(func(req *inventorypb.CreateProductRequest) bool {
                        return req.Name == "New Product" && req.Sku == "NEW-001"
                    })).Return(&inventorypb.CreateProductResponse{
                    Success: true,
                    Message: "Product created successfully",
                    Data: &inventorypb.Product{
                        Id:          "product-new",
                        Name:        "New Product",
                        Sku:         "NEW-001",
                        Price:       149.99,
                        CategoryId:  "category-1",
                    },
                }, nil)

                // Mock event publishing
                kafka.On("PublishEvent", mock.Anything, "inventory.product.created", mock.Anything).Return(nil)
                
                // Mock real-time notification
                redis.On("Publish", mock.Anything, "inventory:notifications", mock.Anything).Return(nil)
            },
            expectedStatus: 201,
        },
        {
            name: "validation error",
            requestBody: CreateProductRequest{
                Name: "", // Invalid - empty name
                SKU:  "INVALID",
            },
            userClaims: &auth.Claims{
                UserID:      "user-123",
                Permissions: []string{"write:inventory"},
            },
            mockSetup: func(grpc *mocks.MockGRPCClient, kafka *mocks.MockKafkaProducer, redis *mocks.MockRedisClient) {
                // No mocks needed for validation error
            },
            expectedStatus: 400,
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            // Setup mocks
            mockGRPC := &mocks.MockGRPCClient{}
            mockKafka := &mocks.MockKafkaProducer{}
            mockRedis := &mocks.MockRedisClient{}
            mockLogger := &mocks.MockLogger{}

            tt.mockSetup(mockGRPC, mockKafka, mockRedis)

            // Create handler
            handler := &InventoryHandler{
                grpcClient:    mockGRPC,
                redisClient:   mockRedis,
                kafkaProducer: mockKafka,
                logger:        mockLogger,
            }

            // Setup Gin with auth middleware mock
            gin.SetMode(gin.TestMode)
            router := gin.New()
            router.Use(func(c *gin.Context) {
                c.Set("user_claims", tt.userClaims)
                c.Next()
            })
            router.POST("/products", handler.CreateProduct)

            // Create request
            body, _ := json.Marshal(tt.requestBody)
            req := httptest.NewRequest("POST", "/products", bytes.NewBuffer(body))
            req.Header.Set("Content-Type", "application/json")
            w := httptest.NewRecorder()

            // Execute request
            router.ServeHTTP(w, req)

            // Assert response
            assert.Equal(t, tt.expectedStatus, w.Code)

            // Verify mocks
            mockGRPC.AssertExpectations(t)
            mockKafka.AssertExpectations(t)
            mockRedis.AssertExpectations(t)
        })
    }
}
```### 10.2 I
ntegration Tests

Create integration tests that verify the complete flow:

```go
// test/integration/inventory_integration_test.go
package integration

import (
    "context"
    "encoding/json"
    "fmt"
    "net/http"
    "strings"
    "testing"
    "time"

    "github.com/gorilla/websocket"
    "github.com/stretchr/testify/assert"
    "github.com/stretchr/testify/require"
    "github.com/stretchr/testify/suite"
)

type InventoryIntegrationTestSuite struct {
    suite.Suite
    server      *TestServer
    client      *http.Client
    accessToken string
    wsConn      *websocket.Conn
}

func (suite *InventoryIntegrationTestSuite) SetupSuite() {
    // Start test server with all dependencies
    suite.server = NewTestServer()
    suite.client = &http.Client{Timeout: 30 * time.Second}
    
    // Authenticate and get access token
    suite.accessToken = suite.authenticateTestUser()
    
    // Establish WebSocket connection for real-time testing
    suite.setupWebSocketConnection()
}

func (suite *InventoryIntegrationTestSuite) TearDownSuite() {
    if suite.wsConn != nil {
        suite.wsConn.Close()
    }
    suite.server.Close()
}

func (suite *InventoryIntegrationTestSuite) TestCompleteInventoryFlow() {
    // Test complete inventory management flow
    
    // 1. Create a product
    product := suite.createTestProduct()
    suite.NotEmpty(product.ID)
    suite.Equal("Integration Test Product", product.Name)
    
    // 2. Verify product appears in product list
    products := suite.getProducts()
    suite.Contains(products, product.ID)
    
    // 3. Create a warehouse
    warehouse := suite.createTestWarehouse()
    suite.NotEmpty(warehouse.ID)
    
    // 4. Add stock to the product in the warehouse
    stock := suite.addStock(product.ID, warehouse.ID, 100)
    suite.Equal(int32(100), stock.Quantity)
    
    // 5. Update stock and verify real-time notification
    suite.updateStockWithNotification(product.ID, warehouse.ID, -10)
    
    // 6. Verify stock history
    history := suite.getStockHistory(product.ID, warehouse.ID)
    suite.Len(history, 2) // Initial stock + update
    
    // 7. Test low stock alert
    suite.updateStockWithLowStockAlert(product.ID, warehouse.ID, -85)
    
    // 8. Update product and verify cache invalidation
    suite.updateProductAndVerifyCache(product.ID)
    
    // 9. Delete product and verify cleanup
    suite.deleteProductAndVerifyCleanup(product.ID)
}

func (suite *InventoryIntegrationTestSuite) TestGraphQLIntegration() {
    // Test GraphQL queries and mutations
    
    // Create test data
    product := suite.createTestProduct()
    warehouse := suite.createTestWarehouse()
    
    // Test GraphQL query
    query := `
        query GetProduct($id: ID!) {
            product(id: $id) {
                id
                name
                sku
                price
                stock {
                    warehouseId
                    quantity
                    availableQuantity
                }
            }
        }
    `
    
    variables := map[string]interface{}{
        "id": product.ID,
    }
    
    result := suite.executeGraphQLQuery(query, variables)
    suite.Equal(product.ID, result["product"].(map[string]interface{})["id"])
    
    // Test GraphQL mutation
    mutation := `
        mutation CreateProduct($input: CreateProductInput!) {
            createProduct(input: $input) {
                success
                message
                product {
                    id
                    name
                    sku
                }
                errors {
                    field
                    message
                }
            }
        }
    `
    
    mutationVars := map[string]interface{}{
        "input": map[string]interface{}{
            "name":        "GraphQL Test Product",
            "sku":         "GQL-001",
            "price":       199.99,
            "categoryId":  "test-category",
        },
    }
    
    mutationResult := suite.executeGraphQLMutation(mutation, mutationVars)
    createResult := mutationResult["createProduct"].(map[string]interface{})
    suite.True(createResult["success"].(bool))
    suite.NotEmpty(createResult["product"].(map[string]interface{})["id"])
}

func (suite *InventoryIntegrationTestSuite) TestWebSocketRealTimeUpdates() {
    // Test real-time WebSocket notifications
    
    product := suite.createTestProduct()
    warehouse := suite.createTestWarehouse()
    
    // Subscribe to product updates
    suite.subscribeToProductUpdates(product.ID)
    
    // Subscribe to stock updates
    suite.subscribeToStockUpdates(product.ID, warehouse.ID)
    
    // Subscribe to low stock alerts
    suite.subscribeToLowStockAlerts()
    
    // Perform operations that should trigger notifications
    notifications := make([]map[string]interface{}, 0)
    
    // Start listening for notifications
    go func() {
        for i := 0; i < 3; i++ { // Expect 3 notifications
            var msg map[string]interface{}
            err := suite.wsConn.ReadJSON(&msg)
            if err != nil {
                suite.T().Errorf("Failed to read WebSocket message: %v", err)
                return
            }
            notifications = append(notifications, msg)
        }
    }()
    
    // Trigger notifications
    suite.addStock(product.ID, warehouse.ID, 50)           // Stock update notification
    suite.updateStock(product.ID, warehouse.ID, -40)       // Stock update notification  
    suite.updateStock(product.ID, warehouse.ID, -8)        // Low stock alert notification
    
    // Wait for notifications
    time.Sleep(2 * time.Second)
    
    // Verify notifications received
    suite.Len(notifications, 3)
    
    // Verify notification types
    notificationTypes := make([]string, len(notifications))
    for i, notif := range notifications {
        notificationTypes[i] = notif["type"].(string)
    }
    
    suite.Contains(notificationTypes, "stock_updated")
    suite.Contains(notificationTypes, "low_stock_alert")
}

func (suite *InventoryIntegrationTestSuite) TestPermissionEnforcement() {
    // Test RBAC permission enforcement
    
    // Create user with limited permissions
    limitedToken := suite.authenticateUserWithPermissions([]string{"read:inventory"})
    
    // Should be able to read products
    products := suite.getProductsWithToken(limitedToken)
    suite.NotNil(products)
    
    // Should NOT be able to create products
    resp := suite.createProductWithToken(limitedToken, CreateProductRequest{
        Name:       "Unauthorized Product",
        SKU:        "UNAUTH-001",
        Price:      99.99,
        CategoryID: "test-category",
    })
    suite.Equal(403, resp.StatusCode)
    
    // Test warehouse management permissions
    warehouseManagerToken := suite.authenticateUserWithPermissions([]string{"manage:warehouses"})
    
    // Should be able to create warehouse
    warehouse := suite.createWarehouseWithToken(warehouseManagerToken)
    suite.NotEmpty(warehouse.ID)
    
    // Regular user should NOT be able to create warehouse
    resp = suite.createWarehouseWithToken(limitedToken, CreateWarehouseRequest{
        Name:    "Unauthorized Warehouse",
        Address: "Test Address",
    })
    suite.Equal(403, resp.StatusCode)
}

func (suite *InventoryIntegrationTestSuite) TestCachingBehavior() {
    // Test caching functionality
    
    product := suite.createTestProduct()
    
    // First request should be cache miss
    start := time.Now()
    result1 := suite.getProduct(product.ID)
    duration1 := time.Since(start)
    
    // Second request should be cache hit (faster)
    start = time.Now()
    result2 := suite.getProduct(product.ID)
    duration2 := time.Since(start)
    
    // Verify same data
    suite.Equal(result1.ID, result2.ID)
    suite.Equal(result1.Name, result2.Name)
    
    // Cache hit should be faster
    suite.True(duration2 < duration1, "Cache hit should be faster than cache miss")
    
    // Update product should invalidate cache
    suite.updateProduct(product.ID, UpdateProductRequest{
        Name:  "Updated Product Name",
        Price: 299.99,
    })
    
    // Next request should be cache miss again
    start = time.Now()
    result3 := suite.getProduct(product.ID)
    duration3 := time.Since(start)
    
    suite.Equal("Updated Product Name", result3.Name)
    suite.True(duration3 > duration2, "After cache invalidation, request should be slower")
}

func (suite *InventoryIntegrationTestSuite) TestEventPublishing() {
    // Test Kafka event publishing
    
    // Setup Kafka consumer to verify events
    consumer := suite.setupKafkaConsumer([]string{
        "inventory.product.created",
        "inventory.stock.updated",
        "inventory.product.updated",
    })
    defer consumer.Close()
    
    events := make([]map[string]interface{}, 0)
    
    // Start consuming events
    go func() {
        for event := range consumer.Events() {
            var eventData map[string]interface{}
            json.Unmarshal(event.Value, &eventData)
            events = append(events, eventData)
        }
    }()
    
    // Perform operations that should publish events
    product := suite.createTestProduct()
    warehouse := suite.createTestWarehouse()
    suite.addStock(product.ID, warehouse.ID, 100)
    suite.updateProduct(product.ID, UpdateProductRequest{Name: "Updated Name"})
    
    // Wait for events to be processed
    time.Sleep(3 * time.Second)
    
    // Verify events were published
    suite.GreaterOrEqual(len(events), 3)
    
    eventTypes := make([]string, len(events))
    for i, event := range events {
        eventTypes[i] = event["event_type"].(string)
    }
    
    suite.Contains(eventTypes, "ProductCreated")
    suite.Contains(eventTypes, "StockUpdated")
    suite.Contains(eventTypes, "ProductUpdated")
}

// Helper methods
func (suite *InventoryIntegrationTestSuite) createTestProduct() *Product {
    req := CreateProductRequest{
        Name:        "Integration Test Product",
        Description: "Test product for integration testing",
        SKU:         fmt.Sprintf("TEST-%d", time.Now().Unix()),
        Price:       99.99,
        CategoryID:  "test-category",
    }
    
    resp := suite.makeAuthenticatedRequest("POST", "/api/v1/inventory/products/", req)
    suite.Equal(201, resp.StatusCode)
    
    var result map[string]interface{}
    json.NewDecoder(resp.Body).Decode(&result)
    
    data := result["data"].(map[string]interface{})
    return &Product{
        ID:    data["id"].(string),
        Name:  data["name"].(string),
        SKU:   data["sku"].(string),
        Price: data["price"].(float64),
    }
}

func (suite *InventoryIntegrationTestSuite) makeAuthenticatedRequest(method, path string, body interface{}) *http.Response {
    var reqBody strings.Reader
    if body != nil {
        jsonBody, _ := json.Marshal(body)
        reqBody = *strings.NewReader(string(jsonBody))
    }
    
    req, _ := http.NewRequest(method, suite.server.URL+path, &reqBody)
    req.Header.Set("Authorization", "Bearer "+suite.accessToken)
    req.Header.Set("Content-Type", "application/json")
    
    resp, err := suite.client.Do(req)
    suite.NoError(err)
    
    return resp
}

func TestInventoryIntegrationSuite(t *testing.T) {
    suite.Run(t, new(InventoryIntegrationTestSuite))
}
```### 10.3 
Load Testing

Create load tests to verify performance under concurrent load:

```go
// test/load/inventory_load_test.go
package load

import (
    "context"
    "encoding/json"
    "fmt"
    "math/rand"
    "sync"
    "testing"
    "time"

    "github.com/stretchr/testify/assert"
)

func TestInventoryLoadTest(t *testing.T) {
    if testing.Short() {
        t.Skip("Skipping load test in short mode")
    }

    // Test configuration
    config := LoadTestConfig{
        BaseURL:           "http://localhost:8080",
        ConcurrentUsers:   100,
        TestDuration:      2 * time.Minute,
        RampUpDuration:    30 * time.Second,
        RequestsPerSecond: 50,
    }

    // Setup test data
    testData := setupInventoryTestData(t, config.BaseURL)
    defer cleanupInventoryTestData(t, config.BaseURL, testData)

    // Run load test scenarios
    results := runInventoryLoadTest(t, config, testData)

    // Verify performance requirements
    assert.Less(t, results.ErrorRate, 0.05, "Error rate should be < 5%")
    assert.Less(t, results.AvgResponseTime, 200*time.Millisecond, "Average response time should be < 200ms")
    assert.Less(t, results.P95ResponseTime, 500*time.Millisecond, "95th percentile should be < 500ms")
    assert.Greater(t, results.RequestsPerSecond, 40.0, "Should handle > 40 RPS")

    // Log results
    t.Logf("Load Test Results:")
    t.Logf("  Total Requests: %d", results.TotalRequests)
    t.Logf("  Successful Requests: %d", results.SuccessfulRequests)
    t.Logf("  Error Rate: %.2f%%", results.ErrorRate*100)
    t.Logf("  Avg Response Time: %v", results.AvgResponseTime)
    t.Logf("  P95 Response Time: %v", results.P95ResponseTime)
    t.Logf("  P99 Response Time: %v", results.P99ResponseTime)
    t.Logf("  Requests/Second: %.2f", results.RequestsPerSecond)
}

func runInventoryLoadTest(t *testing.T, config LoadTestConfig, testData *InventoryTestData) *LoadTestResults {
    ctx, cancel := context.WithTimeout(context.Background(), config.TestDuration)
    defer cancel()

    results := &LoadTestResults{
        StartTime: time.Now(),
    }

    var wg sync.WaitGroup
    var mu sync.Mutex
    
    responseTimes := make([]time.Duration, 0)
    errorCount := 0
    successCount := 0

    // Create worker pool
    for i := 0; i < config.ConcurrentUsers; i++ {
        wg.Add(1)
        go func(workerID int) {
            defer wg.Done()
            
            client := NewLoadTestClient(config.BaseURL)
            
            // Ramp up delay
            rampUpDelay := time.Duration(workerID) * (config.RampUpDuration / time.Duration(config.ConcurrentUsers))
            time.Sleep(rampUpDelay)

            ticker := time.NewTicker(time.Second / time.Duration(config.RequestsPerSecond/config.ConcurrentUsers))
            defer ticker.Stop()

            for {
                select {
                case <-ctx.Done():
                    return
                case <-ticker.C:
                    // Execute random inventory operation
                    operation := selectRandomOperation()
                    start := time.Now()
                    err := executeInventoryOperation(client, operation, testData)
                    duration := time.Since(start)

                    mu.Lock()
                    responseTimes = append(responseTimes, duration)
                    if err != nil {
                        errorCount++
                        t.Logf("Worker %d error: %v", workerID, err)
                    } else {
                        successCount++
                    }
                    mu.Unlock()
                }
            }
        }(i)
    }

    wg.Wait()

    // Calculate results
    results.EndTime = time.Now()
    results.TotalRequests = len(responseTimes)
    results.SuccessfulRequests = successCount
    results.ErrorRate = float64(errorCount) / float64(results.TotalRequests)
    results.RequestsPerSecond = float64(results.TotalRequests) / results.EndTime.Sub(results.StartTime).Seconds()

    if len(responseTimes) > 0 {
        results.AvgResponseTime = calculateAverage(responseTimes)
        results.P95ResponseTime = calculatePercentile(responseTimes, 0.95)
        results.P99ResponseTime = calculatePercentile(responseTimes, 0.99)
    }

    return results
}

func selectRandomOperation() InventoryOperation {
    operations := []InventoryOperation{
        {Type: "get_products", Weight: 40},
        {Type: "get_product", Weight: 25},
        {Type: "get_stock", Weight: 15},
        {Type: "create_product", Weight: 8},
        {Type: "update_stock", Weight: 7},
        {Type: "update_product", Weight: 3},
        {Type: "get_warehouses", Weight: 2},
    }

    totalWeight := 0
    for _, op := range operations {
        totalWeight += op.Weight
    }

    random := rand.Intn(totalWeight)
    currentWeight := 0

    for _, op := range operations {
        currentWeight += op.Weight
        if random < currentWeight {
            return op
        }
    }

    return operations[0] // Fallback
}

func executeInventoryOperation(client *LoadTestClient, operation InventoryOperation, testData *InventoryTestData) error {
    switch operation.Type {
    case "get_products":
        return client.GetProducts(GetProductsParams{
            Page:  rand.Intn(10) + 1,
            Limit: 20,
        })

    case "get_product":
        if len(testData.ProductIDs) == 0 {
            return fmt.Errorf("no test products available")
        }
        productID := testData.ProductIDs[rand.Intn(len(testData.ProductIDs))]
        return client.GetProduct(productID)

    case "get_stock":
        if len(testData.ProductIDs) == 0 || len(testData.WarehouseIDs) == 0 {
            return fmt.Errorf("no test data available")
        }
        productID := testData.ProductIDs[rand.Intn(len(testData.ProductIDs))]
        warehouseID := testData.WarehouseIDs[rand.Intn(len(testData.WarehouseIDs))]
        return client.GetStock(productID, warehouseID)

    case "create_product":
        return client.CreateProduct(CreateProductRequest{
            Name:        fmt.Sprintf("Load Test Product %d", rand.Intn(10000)),
            SKU:         fmt.Sprintf("LOAD-%d", rand.Intn(10000)),
            Price:       float64(rand.Intn(1000)) + 0.99,
            CategoryID:  "load-test-category",
        })

    case "update_stock":
        if len(testData.ProductIDs) == 0 || len(testData.WarehouseIDs) == 0 {
            return fmt.Errorf("no test data available")
        }
        productID := testData.ProductIDs[rand.Intn(len(testData.ProductIDs))]
        warehouseID := testData.WarehouseIDs[rand.Intn(len(testData.WarehouseIDs))]
        change := rand.Intn(21) - 10 // -10 to +10
        return client.UpdateStock(UpdateStockRequest{
            ProductID:      productID,
            WarehouseID:    warehouseID,
            QuantityChange: change,
            Reason:         "Load test adjustment",
        })

    case "update_product":
        if len(testData.ProductIDs) == 0 {
            return fmt.Errorf("no test products available")
        }
        productID := testData.ProductIDs[rand.Intn(len(testData.ProductIDs))]
        return client.UpdateProduct(productID, UpdateProductRequest{
            Name:  fmt.Sprintf("Updated Product %d", rand.Intn(1000)),
            Price: float64(rand.Intn(1000)) + 0.99,
        })

    case "get_warehouses":
        return client.GetWarehouses(GetWarehousesParams{
            Page:  1,
            Limit: 10,
        })

    default:
        return fmt.Errorf("unknown operation type: %s", operation.Type)
    }
}

func setupInventoryTestData(t *testing.T, baseURL string) *InventoryTestData {
    client := NewLoadTestClient(baseURL)
    testData := &InventoryTestData{
        ProductIDs:   make([]string, 0),
        WarehouseIDs: make([]string, 0),
    }

    // Create test products
    for i := 0; i < 50; i++ {
        product := CreateProductRequest{
            Name:        fmt.Sprintf("Load Test Product %d", i),
            SKU:         fmt.Sprintf("LOAD-SETUP-%d", i),
            Price:       99.99,
            CategoryID:  "load-test-category",
        }

        if productID, err := client.CreateProductAndReturnID(product); err == nil {
            testData.ProductIDs = append(testData.ProductIDs, productID)
        }
    }

    // Create test warehouses
    for i := 0; i < 5; i++ {
        warehouse := CreateWarehouseRequest{
            Name:    fmt.Sprintf("Load Test Warehouse %d", i),
            Address: fmt.Sprintf("Test Address %d", i),
        }

        if warehouseID, err := client.CreateWarehouseAndReturnID(warehouse); err == nil {
            testData.WarehouseIDs = append(testData.WarehouseIDs, warehouseID)
        }
    }

    // Add initial stock
    for _, productID := range testData.ProductIDs {
        for _, warehouseID := range testData.WarehouseIDs {
            client.UpdateStock(UpdateStockRequest{
                ProductID:      productID,
                WarehouseID:    warehouseID,
                QuantityChange: 100,
                Reason:         "Initial stock for load testing",
            })
        }
    }

    t.Logf("Created test data: %d products, %d warehouses", len(testData.ProductIDs), len(testData.WarehouseIDs))
    return testData
}

type LoadTestConfig struct {
    BaseURL           string
    ConcurrentUsers   int
    TestDuration      time.Duration
    RampUpDuration    time.Duration
    RequestsPerSecond int
}

type LoadTestResults struct {
    StartTime          time.Time
    EndTime            time.Time
    TotalRequests      int
    SuccessfulRequests int
    ErrorRate          float64
    AvgResponseTime    time.Duration
    P95ResponseTime    time.Duration
    P99ResponseTime    time.Duration
    RequestsPerSecond  float64
}

type InventoryOperation struct {
    Type   string
    Weight int
}

type InventoryTestData struct {
    ProductIDs   []string
    WarehouseIDs []string
}
```## St
ep 11: Deployment Configuration

### 11.1 Update Docker Configuration

Add the inventory service to Docker Compose:

```yaml
# docker-compose.yml
version: '3.8'

services:
  api-gateway:
    build: .
    ports:
      - "8080:8080"
    environment:
      - GRPC_SERVICES_INVENTORY_ADDRESS=inventory-service:50055
      - REDIS_ADDRESS=redis:6379
      - KAFKA_BROKERS=kafka:9092
    depends_on:
      - redis
      - kafka
      - inventory-service
    networks:
      - erp-network

  inventory-service:
    image: inventory-service:latest
    ports:
      - "50055:50055"
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/inventory
      - REDIS_URL=redis://redis:6379
    depends_on:
      - postgres
      - redis
    networks:
      - erp-network

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    networks:
      - erp-network

  kafka:
    image: confluentinc/cp-kafka:latest
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
    depends_on:
      - zookeeper
    networks:
      - erp-network

  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: inventory
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
    volumes:
      - postgres-data:/var/lib/postgresql/data
    networks:
      - erp-network

volumes:
  redis-data:
  postgres-data:

networks:
  erp-network:
    driver: bridge
```

### 11.2 Kubernetes Deployment

Update Kubernetes manifests to include inventory service configuration:

```yaml
# deployments/kubernetes/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: api-gateway-config
data:
  config.yaml: |
    server:
      port: 8080
      host: "0.0.0.0"
    
    grpc:
      services:
        auth:
          address: "auth-service:50051"
          timeout: "10s"
          max_retries: 3
        crm:
          address: "crm-service:50052"
          timeout: "10s"
          max_retries: 3
        hrm:
          address: "hrm-service:50053"
          timeout: "10s"
          max_retries: 3
        finance:
          address: "finance-service:50054"
          timeout: "10s"
          max_retries: 3
        inventory:
          address: "inventory-service:50055"
          timeout: "10s"
          max_retries: 3
    
    redis:
      address: "redis-service:6379"
      db: 0
      pool_size: 10
    
    kafka:
      brokers:
        - "kafka-service:9092"
      client_id: "api-gateway"

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway
  labels:
    app: api-gateway
spec:
  replicas: 3
  selector:
    matchLabels:
      app: api-gateway
  template:
    metadata:
      labels:
        app: api-gateway
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8080"
        prometheus.io/path: "/metrics"
    spec:
      containers:
      - name: gateway
        image: api-gateway:latest
        ports:
        - containerPort: 8080
        env:
        - name: GRPC_SERVICES_INVENTORY_ADDRESS
          value: "inventory-service:50055"
        envFrom:
        - configMapRef:
            name: api-gateway-config
        - secretRef:
            name: api-gateway-secrets
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
        volumeMounts:
        - name: config
          mountPath: /config.yaml
          subPath: config.yaml
      volumes:
      - name: config
        configMap:
          name: api-gateway-config

---
# Inventory Service Deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: inventory-service
  labels:
    app: inventory-service
spec:
  replicas: 2
  selector:
    matchLabels:
      app: inventory-service
  template:
    metadata:
      labels:
        app: inventory-service
    spec:
      containers:
      - name: inventory-service
        image: inventory-service:latest
        ports:
        - containerPort: 50055
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: inventory-secrets
              key: database-url
        - name: REDIS_URL
          value: "redis://redis-service:6379"
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          exec:
            command:
            - /bin/grpc_health_probe
            - -addr=:50055
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          exec:
            command:
            - /bin/grpc_health_probe
            - -addr=:50055
          initialDelaySeconds: 5
          periodSeconds: 5

---
apiVersion: v1
kind: Service
metadata:
  name: inventory-service
  labels:
    app: inventory-service
spec:
  ports:
  - port: 50055
    targetPort: 50055
    protocol: TCP
    name: grpc
  selector:
    app: inventory-service
```

### 11.3 Monitoring Configuration

Add inventory-specific monitoring:

```yaml
# deployments/monitoring/servicemonitor.yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: api-gateway-inventory
  labels:
    app: api-gateway
spec:
  selector:
    matchLabels:
      app: api-gateway
  endpoints:
  - port: http
    path: /metrics
    interval: 30s
    scrapeTimeout: 10s
    relabelings:
    - sourceLabels: [__meta_kubernetes_pod_label_app]
      targetLabel: service
    - sourceLabels: [__meta_kubernetes_pod_name]
      targetLabel: instance

---
# Grafana Dashboard ConfigMap
apiVersion: v1
kind: ConfigMap
metadata:
  name: inventory-dashboard
  labels:
    grafana_dashboard: "1"
data:
  inventory-dashboard.json: |
    {
      "dashboard": {
        "title": "Inventory Service Dashboard",
        "panels": [
          {
            "title": "Inventory API Request Rate",
            "type": "graph",
            "targets": [
              {
                "expr": "rate(http_requests_total{path=~\"/api/v1/inventory.*\"}[5m])",
                "legendFormat": "{{method}} {{path}}"
              }
            ]
          },
          {
            "title": "Inventory API Response Time",
            "type": "graph",
            "targets": [
              {
                "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{path=~\"/api/v1/inventory.*\"}[5m]))",
                "legendFormat": "95th percentile"
              },
              {
                "expr": "histogram_quantile(0.50, rate(http_request_duration_seconds_bucket{path=~\"/api/v1/inventory.*\"}[5m]))",
                "legendFormat": "50th percentile"
              }
            ]
          },
          {
            "title": "Inventory Cache Hit Rate",
            "type": "singlestat",
            "targets": [
              {
                "expr": "rate(redis_cache_hits_total{service=\"inventory\"}[5m]) / (rate(redis_cache_hits_total{service=\"inventory\"}[5m]) + rate(redis_cache_misses_total{service=\"inventory\"}[5m]))",
                "legendFormat": "Hit Rate"
              }
            ]
          },
          {
            "title": "Stock Update Events",
            "type": "graph",
            "targets": [
              {
                "expr": "rate(kafka_messages_published_total{topic=\"inventory.stock.updated\"}[5m])",
                "legendFormat": "Stock Updates/sec"
              }
            ]
          },
          {
            "title": "Low Stock Alerts",
            "type": "graph",
            "targets": [
              {
                "expr": "rate(kafka_messages_published_total{topic=\"inventory.stock.low_stock_alert\"}[5m])",
                "legendFormat": "Low Stock Alerts/sec"
              }
            ]
          },
          {
            "title": "WebSocket Inventory Subscriptions",
            "type": "graph",
            "targets": [
              {
                "expr": "websocket_subscriptions_active{channel=~\"inventory:.*\"}",
                "legendFormat": "{{channel}}"
              }
            ]
          }
        ]
      }
    }
```

## Summary

This comprehensive guide demonstrates how to integrate a new microservice (Inventory Service) with the ERP API Gateway, leveraging all available features:

### ✅ **Completed Integration Features**

1. **Service Registration**: Added inventory service to configuration and gRPC client
2. **Protocol Buffers**: Defined comprehensive proto schema for inventory operations
3. **gRPC Integration**: Implemented client with connection pooling and circuit breakers
4. **REST API**: Created full CRUD REST endpoints with caching and validation
5. **GraphQL Integration**: Added queries, mutations, and subscriptions with DataLoader optimization
6. **WebSocket Real-time**: Implemented real-time notifications for stock updates and alerts
7. **Authentication & Authorization**: Integrated RBAC with inventory-specific permissions
8. **Caching Strategy**: Multi-level caching with appropriate TTL and invalidation
9. **Event Publishing**: Comprehensive Kafka event publishing for business events
10. **Testing**: Unit tests, integration tests, and load tests
11. **Deployment**: Docker and Kubernetes configuration with monitoring

### 🚀 **Key Benefits Achieved**

- **Multi-Protocol Support**: Single service accessible via REST, GraphQL, and WebSocket
- **Real-time Capabilities**: Instant notifications for stock changes and alerts
- **High Performance**: Caching, connection pooling, and optimized data loading
- **Security**: Comprehensive RBAC with granular permissions
- **Scalability**: Horizontal scaling with Redis coordination
- **Observability**: Comprehensive monitoring and event tracking
- **Developer Experience**: Clear APIs, comprehensive testing, and documentation

### 📋 **Integration Checklist**

When adding a new microservice, follow this checklist:

- [ ] Define Protocol Buffer schema
- [ ] Update configuration files
- [ ] Add gRPC client integration
- [ ] Create REST API handlers
- [ ] Implement GraphQL schema and resolvers
- [ ] Add WebSocket real-time features
- [ ] Define permissions and roles
- [ ] Implement caching strategy
- [ ] Add event publishing
- [ ] Write comprehensive tests
- [ ] Update deployment configurations
- [ ] Add monitoring and alerting
- [ ] Update documentation

This integration pattern can be replicated for any new microservice, ensuring consistent architecture, security, and developer experience across the entire ERP system.