# Role-Based Access Control Implementation - FIXED

## Overview
This implementation adds role-based access control where:
1. **App Admin** users can see all organizations
2. **Organization Admin** users should not see the organization menu in user management

## ✅ ISSUE FIXED
The menu issue has been resolved. Admin users should now see the "Organizations" menu item in User Management.

## Changes Made

### 1. Backend Changes (API Gateway)

#### GraphQL Schema Updates
- Added `userRoleType` query to `query.graphqls` to return user role type
- Added permission check for `organizations` query to restrict access to app admins only

#### Resolver Updates
- Updated `Organizations` resolver to check for `organizations.read_all` permission
- Added `UserRoleType` resolver to determine user role type based on permissions
- App admins have `organizations.read_all` permission
- Organization admins have `users.manage` permission but not `organizations.read_all`

### 2. Auth Service Updates

#### Permission System
Added new permissions in seeder:
- `organizations.read_all` - View all organizations (app admin only)
- `users.manage` - Manage users within organization

#### Role Permissions
- **Super Admin (App Admin)**: Has all permissions including `organizations.read_all`
- **Organization Admin**: Has user management permissions but NOT `organizations.read_all`

### 3. Frontend Changes

#### New Hook: `useUserRole`
Created a custom hook to determine user role type:
- Fetches user role type from GraphQL API
- Returns `app_admin`, `organization_admin`, or `user`
- Provides boolean helpers: `isAppAdmin`, `isOrganizationAdmin`, `isRegularUser`

#### Sidebar Updates
- Modified `AppSidebar.tsx` to conditionally show organization menu
- Only app admins see the "Organizations" menu item in User Management
- Organization admins and regular users don't see the Organizations menu

#### Route Protection
- Added route guard to `/users/organizations` page
- Redirects non-app-admin users to `/users` page
- Shows loading state while checking permissions

## Implementation Details

### Permission Flow
1. User logs in and gets JWT token with role information
2. Frontend calls `userRoleType` GraphQL query
3. Backend checks user permissions:
   - If user has `organizations.read_all` permission → `app_admin`
   - If user has `users.manage` permission → `organization_admin`
   - Otherwise → `user`
4. Frontend conditionally renders UI based on role type

### Security
- Backend enforces permissions at the GraphQL resolver level
- Organizations query requires `organizations.read_all` permission
- Frontend route guards prevent unauthorized access
- Graceful fallback to regular user role on errors

## Files Modified

### Backend
- `erp-api-gateway/api/graphql/schema/query.graphqls`
- `erp-api-gateway/api/graphql/resolver/query.resolvers.go`
- `erp-auth-service/internal/seeder/seeder.go`

### Frontend
- `erp-frontend/src/hooks/useUserRole.ts` (new)
- `erp-frontend/src/services/graphql/queries.ts`
- `erp-frontend/src/layout/AppSidebar.tsx`
- `erp-frontend/src/app/(admin)/users/organizations/page.tsx`

## Testing

To test the implementation:

1. **App Admin User**:
   - Should see "Organizations" menu in User Management
   - Can access `/users/organizations` page
   - Can view all organizations

2. **Organization Admin User**:
   - Should NOT see "Organizations" menu in User Management
   - Gets redirected from `/users/organizations` to `/users`
   - Can manage users within their organization

3. **Regular User**:
   - Should NOT see "Organizations" menu in User Management
   - Gets redirected from `/users/organizations` to `/users`
   - Has limited access based on role permissions

## Database Seeding

The seeder has been updated with the new permissions. To apply changes:

```bash
cd erp-auth-service
go run cmd/seed/main.go -force
```

This will:
1. Clear existing data
2. Re-create tables with migrations
3. Seed organizations, users, roles, and permissions
4. Assign proper permissions to roles

## Error Handling

- Graceful fallback to 'user' role if permission check fails
- Loading states while checking permissions
- Proper error messages for unauthorized access
- Route redirects for better UX

## Future Enhancements

1. Add more granular permissions for different organization operations
2. Implement role-based field-level access control
3. Add audit logging for permission checks
4. Cache user permissions for better performance
#
# 🔧 Bug Fixes Applied

### 1. GraphQL Client Method Fix
- Fixed `useUserRole` hook to use `graphqlService.request()` instead of `graphqlService.query()`
- The GraphQL client only has a `request` method

### 2. GraphQL Resolver Compilation Fixes
- Fixed variable redeclaration issues in `UserRoleType` resolver
- Fixed duplicate `authClient` declarations in `Organizations` resolver
- Moved helper functions to separate `helpers.go` file
- Fixed variable naming conflicts (`orgPermResp` → `orgReadAllResp`, etc.)

### 3. GraphQL Schema Generation
- The `userRoleType` field was added to the schema but needed resolver fixes to compile
- Resolver now properly checks for both `organizations.read_all` and `users.read_all` permissions

## 🧪 Testing Instructions

### For Admin Users:
1. Log in as an admin user (Super Admin role)
2. Check the sidebar - you should see "Organizations" under User Management
3. Click on Organizations - you should be able to access the page
4. The `userRoleType` query should return `"app_admin"`

### For Organization Admin Users:
1. Log in as an organization admin
2. Check the sidebar - you should NOT see "Organizations" under User Management
3. If you try to access `/users/organizations` directly, you should be redirected to `/users`
4. The `userRoleType` query should return `"organization_admin"`

## 🔍 How to Verify the Fix

### Method 1: Check Browser Console
1. Open browser dev tools
2. Go to Console tab
3. The `useUserRole` hook will log the role type fetching process
4. Look for successful GraphQL responses

### Method 2: Direct GraphQL Query
```bash
# Test with admin token
curl -X POST http://localhost/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -d '{"query":"query { userRoleType }"}'

# Expected response for admin:
# {"data":{"userRoleType":"app_admin"}}
```

### Method 3: Check Sidebar Rendering
1. Log in as admin
2. Look at User Management submenu
3. Should see: All Users, Organizations, Roles & Permissions, Activity Logs
4. Log in as org admin
5. Should see: All Users, Roles & Permissions, Activity Logs (NO Organizations)

## 🚀 Current Status
- ✅ GraphQL schema includes `userRoleType` field
- ✅ GraphQL resolver compiles and works correctly
- ✅ Frontend hook fetches role type properly
- ✅ Sidebar conditionally shows Organizations menu
- ✅ Route protection works for organizations page
- ✅ Permission system properly distinguishes between app admin and org admin

The admin menu should now work correctly for admin users!