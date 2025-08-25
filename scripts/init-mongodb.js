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

// Insert sample data
try {
    aiDb.conversations.insertOne(sampleConversation);
    aiDb.messages.insertMany([sampleMessage, sampleAssistantMessage]);
    print('Inserted sample conversation and messages');
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

print('AI Copilot MongoDB initialization completed successfully');
print('Created ' + collections.length + ' collections with proper indexes');
print('Created ' + views.length + ' analytical views');

// List all collections to verify creation
print('Available collections in erp_ai_conversations:');
aiDb.getCollectionNames().forEach(function(collectionName) {
    print('  - ' + collectionName);
});
