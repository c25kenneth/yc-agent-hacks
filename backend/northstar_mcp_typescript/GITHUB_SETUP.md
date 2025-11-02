# GitHub Pull Request Setup Guide

This guide explains how to configure your deployed Northstar MCP server to create pull requests on GitHub.

## Prerequisites

1. A GitHub account
2. Access to the repositories where you want to create PRs
3. Ability to set environment variables in your deployment environment

## Step 1: Create a GitHub Personal Access Token (PAT)

1. **Go to GitHub Settings**:
   - Visit https://github.com/settings/tokens
   - Or: GitHub Profile → Settings → Developer settings → Personal access tokens → Tokens (classic)

2. **Generate a New Token**:
   - Click "Generate new token" → "Generate new token (classic)"
   - Give it a descriptive name (e.g., "Northstar MCP Server")
   - Set an expiration (recommended: 90 days or 1 year for production)

3. **Select Required Scopes**:
   The token needs the following permissions:
   - ✅ **`repo`** (Full control of private repositories)
     - This includes:
       - `repo:status` - Access commit status
       - `repo_deployment` - Access deployment status
       - `public_repo` - Access public repositories
       - `repo:invite` - Access repository invitations
       - `security_events` - Read and write security events
   
   **Important**: The `repo` scope is required for:
   - Cloning repositories (including private ones)
   - Creating branches
   - Pushing code
   - Creating pull requests

4. **Generate and Copy the Token**:
   - Click "Generate token"
   - **IMPORTANT**: Copy the token immediately - you won't be able to see it again!
   - Store it securely (use a password manager)

## Step 2: Set Environment Variable in Your Deployment

### For Metorial Deployments

If you deployed via Metorial, set the environment variable in your deployment configuration:

```bash
GITHUB_TOKEN=ghp_your_token_here
```

**How to set it in Metorial:**
1. Go to your Metorial dashboard
2. Navigate to your deployment
3. Find "Environment Variables" or "Config" section
4. Add `GITHUB_TOKEN` with your token value
5. Save and restart the deployment

### For Other Deployments

#### Docker/Container Deployments
```bash
docker run -e GITHUB_TOKEN=ghp_your_token_here ...
```

#### Vercel/Netlify
- Add in your project settings under "Environment Variables"
- Make sure to add it to Production, Preview, and Development environments if needed

#### Railway/Fly.io
- Add via their dashboard or CLI:
  ```bash
  railway variables set GITHUB_TOKEN=ghp_your_token_here
  # or
  fly secrets set GITHUB_TOKEN=ghp_your_token_here
  ```

#### Manual Server Setup
```bash
export GITHUB_TOKEN=ghp_your_token_here
```

Or add to your `.env` file (if using locally):
```bash
GITHUB_TOKEN=ghp_your_token_here
```

## Step 3: Verify the Setup

### Test the Configuration

Once your server is deployed with the `GITHUB_TOKEN` set, you can test it by:

1. **Using the MCP Tool**:
   - Call the `execute_code_change` tool via MCP
   - Provide:
     - `instruction`: A test change description
     - `update_block`: Some test code changes
     - `repo`: A repository you have access to (format: `owner/repo`)
     - `file_path`: Path to a file in that repo

2. **Check for Errors**:
   - If you get authentication errors, verify:
     - Token is correct (no extra spaces)
     - Token has `repo` scope
     - Token hasn't expired
     - Repository exists and is accessible

### Common Issues

#### Error: "GITHUB_TOKEN not found in environment"
- **Solution**: Make sure the environment variable is set in your deployment
- **Check**: Verify the variable name is exactly `GITHUB_TOKEN` (case-sensitive)

#### Error: "Your GITHUB_TOKEN may be invalid or expired"
- **Solution**: 
  - Generate a new token
  - Make sure it has the `repo` scope
  - Update the environment variable

#### Error: "Repository 'owner/repo' not found or you don't have access"
- **Solution**:
  - Verify the repository exists
  - Make sure your GitHub account has access to the repository
  - For private repos, ensure the token belongs to an account with access

#### Error: "Failed to commit and push changes"
- **Solution**:
  - Verify the token has write access to the repository
  - Check that the base branch exists (usually `main` or `master`)
  - Ensure you're not trying to push to a protected branch directly

## Step 4: Repository Access

### Public Repositories
- Your token will automatically have access to public repositories
- No additional setup needed

### Private Repositories
- The token must belong to an account that has access to the private repository
- You may need to:
  - Add the account (whose token you're using) as a collaborator
  - Or use an organization token with appropriate permissions

### Organization Repositories
- If using a personal token:
  - Make sure the account is a member of the organization
  - Token has appropriate permissions for the organization
- For organization-wide access:
  - Consider using a GitHub App instead of a PAT
  - Or use a fine-grained PAT with organization permissions

## Security Best Practices

1. **Use Fine-Grained Tokens (Recommended)**:
   - GitHub now supports fine-grained personal access tokens
   - These allow more granular permissions
   - Go to: Settings → Developer settings → Personal access tokens → Fine-grained tokens

2. **Set Expiration Dates**:
   - Don't create tokens that never expire
   - Set reasonable expiration dates (90 days - 1 year)
   - Rotate tokens periodically

3. **Limit Scope**:
   - Only grant the minimum required permissions
   - The `repo` scope is required for PR creation, but avoid broader scopes if possible

4. **Monitor Token Usage**:
   - Regularly review active tokens in GitHub settings
   - Revoke tokens that are no longer needed
   - Check GitHub audit logs for suspicious activity

5. **Store Securely**:
   - Never commit tokens to version control
   - Use environment variables or secret management services
   - Don't log tokens in application logs

## Advanced: Using GitHub Apps (Optional)

For better security and organization-wide access, consider using GitHub Apps:

1. Create a GitHub App in your organization
2. Install it on repositories
3. Generate an installation token
4. Use the installation token instead of a PAT

This is more complex but provides better security and scalability.

## Troubleshooting

### Testing Token Manually

You can test your token directly via GitHub API:

```bash
curl -H "Authorization: token YOUR_TOKEN" https://api.github.com/user
```

If successful, this returns your GitHub user information.

### Checking Token Permissions

```bash
curl -H "Authorization: token YOUR_TOKEN" https://api.github.com/user
# Check the response - it will show scopes if token is valid
```

### Testing Repository Access

```bash
curl -H "Authorization: token YOUR_TOKEN" https://api.github.com/repos/OWNER/REPO
```

If you get a 200 response, you have access. If you get 404, check:
- Repository name is correct
- You have access to the repository
- Token has appropriate permissions

## Next Steps

Once configured:
1. Your MCP server can now clone repositories
2. Create branches with changes
3. Push code to GitHub
4. Create pull requests automatically

The `execute_code_change` tool will handle all of this automatically when called!

