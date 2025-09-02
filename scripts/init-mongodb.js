// MongoDB Database Initialization Script for AI Copilot Service
// This script creates collections and indexes for AI conversations and analytics

// Switch to admin database for authentication
db = db.getSiblingDB('admin');

// Authenticate as root user
db.auth('root', 'password');

// Switch to AI conversations database
const aiDb = db.getSiblingDB('erp_ai_conversations');

// Create collections with proper indexes
const collections = [
    {
        name: 'conversations',
        indexes: [
            { key: { organization_id: 1, user_id: 1 }, name: 'org_user_idx' },
            { key: { created_at: -1 }, name: 'created_at_idx' },
            { key: { status: 1 }, name: 'status_idx' },
            { key: { title: 'text' }, name: 'title_text_idx' }
        ]
    },
    {
        name: 'messages',
        indexes: [
            { key: { conversation_id: 1 }, name: 'conversation_idx' },
            { key: { user_id: 1 }, name: 'user_idx' },
            { key: { created_at: -1 }, name: 'created_at_idx' },
            { key: { role: 1 }, name: 'role_idx' },
            { key: { content: 'text' }, name: 'content_text_idx' }
        ]
    },
    {
        name: 'embeddings',
        indexes: [
            { key: { organization_id: 1 }, name: 'org_idx' },
            { key: { document_type: 1 }, name: 'doc_type_idx' },
            { key: { created_at: -1 }, name: 'created_at_idx' }
        ]
    },
    {
        name: 'training_data',
        indexes: [
            { key: { organization_id: 1 }, name: 'org_idx' },
            { key: { data_type: 1 }, name: 'data_type_idx' },
            { key: { quality_score: -1 }, name: 'quality_idx' },
            { key: { created_at: -1 }, name: 'created_at_idx' }
        ]
    },
    {
        name: 'agent_logs',
        indexes: [
            { key: { organization_id: 1 }, name: 'org_idx' },
            { key: { agent_type: 1 }, name: 'agent_type_idx' },
            { key: { status: 1 }, name: 'status_idx' },
            { key: { created_at: -1 }, name: 'created_at_idx' }
        ]
    },
    {
        name: 'user_preferences',
        indexes: [
            { key: { organization_id: 1, user_id: 1 }, name: 'org_user_idx', unique: true },
            { key: { preferences: 1 }, name: 'preferences_idx' }
        ]
    },
    {
        name: 'conversation_analytics',
        indexes: [
            { key: { organization_id: 1 }, name: 'org_idx' },
            { key: { date: 1 }, name: 'date_idx' },
            { key: { user_id: 1 }, name: 'user_idx' },
            { key: { metrics: 1 }, name: 'metrics_idx' }
        ]
    },
    {
        name: 'memories',
        indexes: [
            { key: { organization_id: 1, user_id: 1 }, name: 'org_user_idx' },
            { key: { memory_type: 1 }, name: 'memory_type_idx' },
            { key: { importance: -1 }, name: 'importance_idx' },
            { key: { created_at: -1 }, name: 'created_at_idx' },
            { key: { content: 'text' }, name: 'content_text_idx' },
            { key: { tags: 1 }, name: 'tags_idx' },
            { key: { expires_at: 1 }, name: 'expires_at_idx' }
        ]
    },
    {
        name: 'contexts',
        indexes: [
            { key: { organization_id: 1, user_id: 1 }, name: 'org_user_idx' },
            { key: { context_type: 1 }, name: 'context_type_idx' },
            { key: { conversation_id: 1 }, name: 'conversation_idx' },
            { key: { created_at: -1 }, name: 'created_at_idx' },
            { key: { relevance_score: -1 }, name: 'relevance_idx' },
            { key: { expires_at: 1 }, name: 'expires_at_idx' }
        ]
    },
    {
        name: 'knowledge_base',
        indexes: [
            { key: { organization_id: 1 }, name: 'org_idx' },
            { key: { document_type: 1 }, name: 'doc_type_idx' },
            { key: { source: 1 }, name: 'source_idx' },
            { key: { created_at: -1 }, name: 'created_at_idx' },
            { key: { title: 'text', content: 'text' }, name: 'content_text_idx' },
            { key: { tags: 1 }, name: 'tags_idx' },
            { key: { version: -1 }, name: 'version_idx' }
        ]
    },
    {
        name: 'reasoning_sessions',
        indexes: [
            { key: { organization_id: 1, user_id: 1 }, name: 'org_user_idx' },
            { key: { conversation_id: 1 }, name: 'conversation_idx' },
            { key: { session_id: 1 }, name: 'session_idx', unique: true },
            { key: { created_at: -1 }, name: 'created_at_idx' },
            { key: { status: 1 }, name: 'status_idx' }
        ]
    },
    {
        name: 'background_jobs',
        indexes: [
            { key: { organization_id: 1 }, name: 'org_idx' },
            { key: { job_type: 1 }, name: 'job_type_idx' },
            { key: { status: 1 }, name: 'status_idx' },
            { key: { priority: -1 }, name: 'priority_idx' },
            { key: { scheduled_at: 1 }, name: 'scheduled_at_idx' },
            { key: { created_at: -1 }, name: 'created_at_idx' }
        ]
    },
    {
        name: 'system_commands',
        indexes: [
            { key: { organization_id: 1, user_id: 1 }, name: 'org_user_idx' },
            { key: { command: 1 }, name: 'command_idx' },
            { key: { status: 1 }, name: 'status_idx' },
            { key: { executed_at: -1 }, name: 'executed_at_idx' },
            { key: { success: 1 }, name: 'success_idx' }
        ]
    },
    {
        name: 'api_access_logs',
        indexes: [
            { key: { organization_id: 1, user_id: 1 }, name: 'org_user_idx' },
            { key: { endpoint: 1 }, name: 'endpoint_idx' },
            { key: { method: 1 }, name: 'method_idx' },
            { key: { status_code: 1 }, name: 'status_code_idx' },
            { key: { timestamp: -1 }, name: 'timestamp_idx' }
        ]
    }
];

// Create collections and indexes
collections.forEach(function(collection) {
    print('Creating collection: ' + collection.name);
    
    // Create collection if it doesn't exist
    if (!aiDb.getCollectionNames().includes(collection.name)) {
        aiDb.createCollection(collection.name);
        print('Created collection: ' + collection.name);
    }
    
    // Create indexes
    collection.indexes.forEach(function(index) {
        try {
            aiDb[collection.name].createIndex(index.key, { 
                name: index.name,
                unique: index.unique || false,
                background: true
            });
            print('Created index: ' + index.name + ' on collection: ' + collection.name);
        } catch (e) {
            if (e.code !== 85) { // 85 is duplicate key error
                print('Warning: Could not create index ' + index.name + ' on ' + collection.name + ': ' + e.message);
            }
        }
    });
});

// Create a user for the AI conversations database
try {
    aiDb.createUser({
        user: 'ai_copilot_user',
        pwd: 'ai_copilot_password',
        roles: [
            { role: 'readWrite', db: 'erp_ai_conversations' },
            { role: 'dbAdmin', db: 'erp_ai_conversations' }
        ]
    });
    print('Created user for AI Copilot database');
} catch (e) {
    if (e.code !== 11000) { // 11000 is duplicate key error
        print('Warning: Could not create user for AI Copilot database: ' + e.message);
    }
}

// Insert sample data for testing
const sampleConversation = {
    _id: ObjectId(),
    organization_id: '00000000-0000-0000-0000-000000000001',
    user_id: '00000000-0000-0000-0000-000000000002',
    title: 'Sample AI Conversation',
    status: 'active',
    created_at: new Date(),
    updated_at: new Date(),
    metadata: {
        source: 'system',
        tags: ['sample', 'test'],
        priority: 'low'
    }
};

const sampleMessage = {
    _id: ObjectId(),
    conversation_id: sampleConversation._id,
    user_id: '00000000-0000-0000-0000-000000000002',
    role: 'user',
    content: 'Hello, how can you help me with my ERP system?',
    created_at: new Date(),
    metadata: {
        tokens_used: 15,
        model_used: 'gpt-4',
        confidence: 0.95
    }
};

const sampleAssistantMessage = {
    _id: ObjectId(),
    conversation_id: sampleConversation._id,
    user_id: null,
    role: 'assistant',
    content: 'Hello! I\'m your AI Copilot assistant. I can help you with various ERP tasks including:\n\n- Financial reports and analytics\n- Inventory management\n- Employee and HR operations\n- Customer relationship management\n- Process automation\n\nWhat would you like to work on today?',
    created_at: new Date(),
    metadata: {
        tokens_used: 45,
        model_used: 'gpt-4',
        confidence: 0.92,
        agent_type: 'help_agent'
    }
};

// Sample data for new collections
const sampleMemory = {
    _id: ObjectId(),
    organization_id: '00000000-0000-0000-0000-000000000001',
    user_id: '00000000-0000-0000-0000-000000000002',
    memory_type: 'conversation_context',
    content: 'User frequently asks about sales reports and prefers detailed analytics',
    importance: 0.8,
    tags: ['sales', 'analytics', 'preference'],
    context: {
        conversation_id: sampleConversation._id,
        query_count: 5,
        last_accessed: new Date()
    },
    created_at: new Date(),
    expires_at: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000) // 30 days
};

const sampleContext = {
    _id: ObjectId(),
    organization_id: '00000000-0000-0000-0000-000000000001',
    user_id: '00000000-0000-0000-0000-000000000002',
    conversation_id: sampleConversation._id,
    context_type: 'user_session',
    data: {
        current_task: 'sales_analysis',
        active_filters: ['Q4_2024', 'region_north'],
        preferred_format: 'detailed_charts'
    },
    relevance_score: 0.9,
    created_at: new Date(),
    expires_at: new Date(Date.now() + 24 * 60 * 60 * 1000) // 24 hours
};

const sampleKnowledgeBase = {
    _id: ObjectId(),
    organization_id: '00000000-0000-0000-0000-000000000001',
    document_type: 'user_guide',
    title: 'ERP Sales Module Documentation',
    content: 'The sales module provides comprehensive tools for managing customer relationships, tracking sales performance, and generating detailed reports.',
    source: 'internal_docs',
    tags: ['sales', 'documentation', 'user_guide'],
    version: 1,
    metadata: {
        author: 'system',
        file_path: '/docs/sales-module.md',
        last_updated: new Date()
    },
    created_at: new Date()
};

const sampleTrainingData = {
    _id: ObjectId(),
    organization_id: '00000000-0000-0000-0000-000000000001',
    data_type: 'conversation_pair',
    input: 'Show me sales performance for this quarter',
    output: 'I\'ll help you analyze the sales performance for Q4 2024. Let me retrieve the latest data from your sales module.',
    quality_score: 0.95,
    metadata: {
        model_used: 'gpt-4',
        user_rating: 5,
        conversation_id: sampleConversation._id,
        reasoning_steps: [
            'Identified request for sales data',
            'Determined time period (current quarter)',
            'Prepared to access sales module data'
        ]
    },
    created_at: new Date()
};

const sampleReasoningSession = {
    _id: ObjectId(),
    session_id: 'reasoning_' + new Date().getTime(),
    organization_id: '00000000-0000-0000-0000-000000000001',
    user_id: '00000000-0000-0000-0000-000000000002',
    conversation_id: sampleConversation._id,
    steps: [
        {
            step_number: 1,
            step_type: 'thinking',
            title: 'Analyzing user request',
            description: 'Processing sales data request',
            source: 'reasoning_engine',
            status: 'completed',
            processing_time: 0.2
        }
    ],
    status: 'completed',
    total_steps: 5,
    processing_time: 2.1,
    created_at: new Date()
};

// Insert sample data
try {
    aiDb.conversations.insertOne(sampleConversation);
    aiDb.messages.insertMany([sampleMessage, sampleAssistantMessage]);
    aiDb.memories.insertOne(sampleMemory);
    aiDb.contexts.insertOne(sampleContext);
    aiDb.knowledge_base.insertOne(sampleKnowledgeBase);
    aiDb.training_data.insertOne(sampleTrainingData);
    aiDb.reasoning_sessions.insertOne(sampleReasoningSession);
    print('Inserted sample data for all collections');
} catch (e) {
    print('Warning: Could not insert sample data: ' + e.message);
}

// Create views for analytics
const views = [
    {
        name: 'conversation_stats',
        pipeline: [
            {
                $group: {
                    _id: {
                        organization_id: '$organization_id',
                        date: { $dateToString: { format: '%Y-%m-%d', date: '$created_at' } }
                    },
                    total_conversations: { $sum: 1 },
                    active_conversations: { $sum: { $cond: [{ $eq: ['$status', 'active'] }, 1, 0] } },
                    avg_messages: { $avg: '$message_count' }
                }
            },
            { $sort: { '_id.date': -1 } }
        ]
    },
    {
        name: 'user_activity',
        pipeline: [
            {
                $lookup: {
                    from: 'messages',
                    localField: '_id',
                    foreignField: 'conversation_id',
                    as: 'messages'
                }
            },
            {
                $group: {
                    _id: '$user_id',
                    total_conversations: { $sum: 1 },
                    total_messages: { $sum: { $size: '$messages' } },
                    last_activity: { $max: '$updated_at' }
                }
            },
            { $sort: { total_messages: -1 } }
        ]
    }
];

// Create views
views.forEach(function(view) {
    try {
        aiDb.createView(view.name, 'conversations', view.pipeline);
        print('Created view: ' + view.name);
    } catch (e) {
        print('Warning: Could not create view ' + view.name + ': ' + e.message);
    }
});

// Create TTL indexes for automatic cleanup
try {
    aiDb.memories.createIndex({ "expires_at": 1 }, { expireAfterSeconds: 0 });
    aiDb.contexts.createIndex({ "expires_at": 1 }, { expireAfterSeconds: 0 });
    aiDb.reasoning_sessions.createIndex({ "created_at": 1 }, { expireAfterSeconds: 7 * 24 * 60 * 60 }); // 7 days
    print('Created TTL indexes for automatic cleanup');
} catch (e) {
    print('Warning: Could not create TTL indexes: ' + e.message);
}

print('AI Copilot MongoDB initialization completed successfully');
print('Created ' + collections.length + ' collections with proper indexes');
print('Created ' + views.length + ' analytical views');
print('Added comprehensive sample data for testing');
print('Configured automatic cleanup for temporary data');

// List all collections to verify creation
print('Available collections in erp_ai_conversations:');
aiDb.getCollectionNames().forEach(function(collectionName) {
    print('  - ' + collectionName);
});
