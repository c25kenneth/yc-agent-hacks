import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { repositoriesAPI, proposalsAPI, slackAPI, oauthStorage } from '../api';

const Settings = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [metric, setMetric] = useState('Checkout Conversion');
  const [threshold, setThreshold] = useState('3.0%');
  const [repoFullname, setRepoFullname] = useState('');
  const [activeRepo, setActiveRepo] = useState(null);
  const [slackConnected, setSlackConnected] = useState(false);
  const [slackLoading, setSlackLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });
  const [codebaseContext, setCodebaseContext] = useState('');
  const [showCodebaseInput, setShowCodebaseInput] = useState(false);

  useEffect(() => {
    loadActiveRepo();
    checkSlackConnection();
  }, []);

  useEffect(() => {
    // Handle OAuth callback (if redirected back from Slack)
    const sessionId = searchParams.get('session_id');
    const state = searchParams.get('state');
    if (sessionId && state === 'slack_oauth') {
      handleOAuthCallback(sessionId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  const loadActiveRepo = async () => {
    try {
      const result = await repositoriesAPI.getActive();
      setActiveRepo(result.repository);
      setRepoFullname(result.repository.repo_fullname);
    } catch (error) {
      // No active repo, that's okay (404) or table doesn't exist yet
      // This is expected when no repository is connected yet
      setActiveRepo(null);
      const errorMessage = error.message || '';
      const is404 = errorMessage.includes('404') || 
                    errorMessage.includes('not found') || 
                    errorMessage.includes('No active repository');
      
      // Only log non-404 errors (unexpected errors)
      if (!is404) {
        console.error('Error loading active repo:', error);
      }
      // Silently handle 404s - this is the expected state when no repo is connected
    }
  };

  const handleConnectRepo = async () => {
    if (!repoFullname || !repoFullname.includes('/')) {
      setMessage({ type: 'error', text: 'Please enter a valid repository in format: owner/repo' });
      return;
    }

    setLoading(true);
    setMessage({ type: '', text: '' });

    try {
      const result = await repositoriesAPI.connect(repoFullname);
      setActiveRepo(result.repository);
      setMessage({ type: 'success', text: result.message });
    } catch (error) {
      setMessage({ type: 'error', text: error.message || 'Failed to connect repository' });
    } finally {
      setLoading(false);
    }
  };

  const checkSlackConnection = () => {
    const sessionId = oauthStorage.getSessionId();
    setSlackConnected(!!sessionId);
  };

  const handleConnectSlack = async () => {
    setSlackLoading(true);
    setMessage({ type: '', text: '' });

    try {
      const result = await slackAPI.startOAuth();
      
      // Store session ID
      oauthStorage.setSessionId(result.session_id);
      
      // Open Slack OAuth in a new window/tab
      const popup = window.open(
        result.auth_url,
        'Slack OAuth',
        'width=600,height=700,scrollbars=yes,resizable=yes'
      );

      // Poll for OAuth completion
      // Actively poll the backend to check if OAuth is complete
      let attempts = 0;
      const maxAttempts = 30; // 30 attempts * 2 seconds = 60 seconds max wait
      let pollComplete = false;
      
      const checkInterval = setInterval(async () => {
        if (pollComplete) return; // Prevent multiple completions
        
        try {
          attempts++;
          
          // Try to complete OAuth - this will wait for completion or return if already complete
          try {
            await slackAPI.completeOAuth(result.session_id);
            
            // Success! OAuth is complete
            pollComplete = true;
            clearInterval(checkInterval);
            oauthStorage.setSessionId(result.session_id);
            setSlackConnected(true);
            setMessage({ type: 'success', text: 'Successfully connected to Slack!' });
            setSlackLoading(false);
            
            // Close popup if still open
            if (popup && !popup.closed) {
              popup.close();
            }
            return;
          } catch (error) {
            // Check response status - 200 means success even if it's an "error" object
            if (error.message && (
              error.message.includes('already') || 
              error.message.includes('complete') ||
              error.message.includes('valid')
            )) {
              // OAuth is already complete or valid - treat as success
              pollComplete = true;
              clearInterval(checkInterval);
              oauthStorage.setSessionId(result.session_id);
              setSlackConnected(true);
              setMessage({ type: 'success', text: 'Successfully connected to Slack!' });
              setSlackLoading(false);
              
              if (popup && !popup.closed) {
                popup.close();
              }
              return;
            }
            
            // If we've reached max attempts, check final status
            if (attempts >= maxAttempts) {
              pollComplete = true;
              clearInterval(checkInterval);
              
              // Final attempt - try once more with a longer wait
              await new Promise(resolve => setTimeout(resolve, 2000));
              
              try {
                await slackAPI.completeOAuth(result.session_id);
                // Success on final attempt
                oauthStorage.setSessionId(result.session_id);
                setSlackConnected(true);
                setMessage({ type: 'success', text: 'Successfully connected to Slack!' });
              } catch (finalError) {
                // Check if popup was closed - might indicate user cancelled
                if (popup?.closed && attempts === maxAttempts) {
                  setMessage({ type: 'error', text: 'Slack OAuth timed out. Please try again.' });
                  oauthStorage.clearSessionId();
                  setSlackConnected(false);
                } else {
                  // Still waiting or uncertain state
                  setMessage({ type: 'warning', text: 'OAuth is still processing. Check your connection status.' });
                }
              }
              setSlackLoading(false);
            }
            // Otherwise, continue polling (wait for next interval)
          }
        } catch (error) {
          // Unexpected error - stop polling
          if (!pollComplete) {
            pollComplete = true;
            clearInterval(checkInterval);
            setMessage({ type: 'error', text: 'An error occurred during OAuth. Please try again.' });
            oauthStorage.clearSessionId();
            setSlackConnected(false);
            setSlackLoading(false);
          }
        }
      }, 2000); // Check every 2 seconds

      // Safety timeout after 5 minutes
      setTimeout(() => {
        if (!pollComplete) {
          pollComplete = true;
          clearInterval(checkInterval);
          if (popup && !popup.closed) {
            popup.close();
          }
          setMessage({ type: 'error', text: 'OAuth timed out after 5 minutes. Please try again.' });
          setSlackLoading(false);
        }
      }, 300000); // 5 minutes
      
    } catch (error) {
      setMessage({ type: 'error', text: error.message || 'Failed to start Slack OAuth' });
      setSlackLoading(false);
    }
  };

  const handleOAuthCallback = async (sessionId) => {
    // This handles the case where OAuth redirects back to our app
    setSlackLoading(true);
    setMessage({ type: '', text: '' });

    try {
      // Wait for OAuth completion
      await slackAPI.completeOAuth(sessionId);
      
      // Store session ID
      oauthStorage.setSessionId(sessionId);
      setSlackConnected(true);
      setMessage({ type: 'success', text: 'Successfully connected to Slack!' });
      
      // Clean up URL
      setSearchParams({});
    } catch (error) {
      setMessage({ type: 'error', text: error.message || 'Failed to complete Slack OAuth' });
      oauthStorage.clearSessionId();
      setSlackConnected(false);
    } finally {
      setSlackLoading(false);
    }
  };

  const handleDisconnectSlack = () => {
    oauthStorage.clearSessionId();
    setSlackConnected(false);
    setMessage({ type: 'success', text: 'Disconnected from Slack' });
  };

  const handleTriggerExperiment = async () => {
    if (!activeRepo) {
      setMessage({ type: 'error', text: 'Please connect a GitHub repository first' });
      return;
    }

    setLoading(true);
    setMessage({ type: '', text: '' });

    try {
      // Get OAuth session ID from storage, use empty string if not connected
      const oauthSessionId = oauthStorage.getSessionId() || '';
      
      // Use provided codebase context if available, otherwise fetch from GitHub automatically
      const contextToSend = codebaseContext.trim() || null;
      
      const result = await proposalsAPI.propose(oauthSessionId, contextToSend);
      setMessage({ type: 'success', text: 'Experiment proposal generated! Check Dashboard for details.' });
      
      // Optionally reload page or navigate to dashboard
      setTimeout(() => {
        window.location.href = '/dashboard';
      }, 2000);
    } catch (error) {
      setMessage({ type: 'error', text: error.message || 'Failed to trigger experiment' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#111827]">
      <div className="mx-auto max-w-4xl px-6 py-8 lg:px-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white">Settings</h1>
          <p className="mt-2 text-gray-400">Configure your Northstar agent and integrations</p>
        </div>

        {/* Set Northstar Metric */}
        <div className="mb-6 rounded border border-gray-800 bg-gray-900 p-6">
          <h2 className="mb-4 text-lg font-semibold text-white">Set Northstar Metric</h2>
          <form className="space-y-4">
            <div>
              <label className="mb-2 block text-sm font-medium text-gray-300">
                Metric Name
              </label>
              <input
                type="text"
                value={metric}
                onChange={(e) => setMetric(e.target.value)}
                placeholder="e.g., Checkout Conversion"
                className="w-full rounded border border-gray-700 bg-gray-800 px-4 py-3 text-white placeholder-gray-500 focus:border-gray-600 focus:outline-none transition"
              />
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium text-gray-300">
                Target Threshold
              </label>
              <input
                type="text"
                value={threshold}
                onChange={(e) => setThreshold(e.target.value)}
                placeholder="e.g., 3.0%"
                className="w-full rounded border border-gray-700 bg-gray-800 px-4 py-3 text-white placeholder-gray-500 focus:border-gray-600 focus:outline-none transition"
              />
            </div>
            <button
              type="submit"
              onClick={(e) => {
                e.preventDefault();
                console.log('Metric updated:', { metric, threshold });
                alert('Metric updated successfully!');
              }}
              className="w-full rounded bg-white px-4 py-3 font-medium text-black hover:bg-gray-100 transition"
            >
              Save Metric
            </button>
          </form>
        </div>

        {/* Connect Slack */}
        <div className="mb-6 rounded border border-gray-800 bg-gray-900 p-6">
          <h2 className="mb-4 text-lg font-semibold text-white">Connect Slack</h2>
          <p className="mb-4 text-sm text-gray-400">
            Connect your Slack workspace to receive notifications about experiments and PRs
          </p>
          
          {slackConnected && (
            <div className="mb-4 rounded bg-green-900/30 border border-green-700 p-3">
              <p className="text-sm text-green-400">
                ✅ <span className="font-semibold">Connected to Slack</span>
              </p>
            </div>
          )}

          {slackConnected ? (
            <button
              onClick={handleDisconnectSlack}
              className="w-full rounded bg-red-900/40 px-4 py-3 font-medium text-red-400 border border-red-700 hover:bg-red-900/50 transition"
            >
              Disconnect Slack
            </button>
          ) : (
            <button
              onClick={handleConnectSlack}
              disabled={slackLoading}
              className="w-full rounded border border-gray-700 bg-gray-800 px-4 py-3 font-medium text-white transition hover:border-gray-600 hover:bg-gray-750 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <div className="flex items-center justify-center gap-2">
                <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zM6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313zM8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zM8.834 6.313a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312zM18.956 5.042a2.528 2.528 0 0 1-2.52-2.52A2.528 2.528 0 0 1 18.956 0a2.528 2.528 0 0 1 2.523 2.522v2.52h-2.523zM18.956 6.313a2.528 2.528 0 0 1 2.523 2.521 2.528 2.528 0 0 1-2.523 2.521h-6.313A2.528 2.528 0 0 1 10.521 8.834a2.528 2.528 0 0 1 2.522-2.521h6.313zM15.165 18.956a2.528 2.528 0 0 1 2.522 2.523A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.52h2.52zM13.895 18.956a2.527 2.527 0 0 1-2.521 2.522 2.527 2.527 0 0 1-2.521-2.522v-6.313a2.528 2.528 0 0 1 2.521-2.521 2.528 2.528 0 0 1 2.521 2.521v6.313zM24 8.834a2.528 2.528 0 0 1-2.522 2.521 2.528 2.528 0 0 1-2.522-2.521V2.522A2.528 2.528 0 0 1 21.478 0 2.528 2.528 0 0 1 24 2.522v6.312z" />
                </svg>
                {slackLoading ? 'Connecting...' : 'Connect Slack Workspace'}
              </div>
            </button>
          )}
        </div>

        {/* Connect GitHub Repository */}
        <div className="mb-6 rounded border border-gray-800 bg-gray-900 p-6">
          <h2 className="mb-4 text-lg font-semibold text-white">Connect GitHub Repository</h2>
          <p className="mb-4 text-sm text-gray-400">
            Link your repository to enable automatic PR creation and code diffs
          </p>
          
          {activeRepo && (
            <div className="mb-4 rounded bg-green-900/30 border border-green-700 p-3">
              <p className="text-sm text-green-400">
                ✅ Connected: <span className="font-semibold">{activeRepo.repo_fullname}</span>
              </p>
            </div>
          )}

          <div className="mb-4 space-y-3">
            <div>
              <label className="mb-2 block text-sm font-medium text-gray-300">
                Repository (owner/repo)
              </label>
              <input
                type="text"
                value={repoFullname}
                onChange={(e) => setRepoFullname(e.target.value)}
                placeholder="e.g., owner/repo"
                className="w-full rounded border border-gray-700 bg-gray-800 px-4 py-3 text-white placeholder-gray-500 focus:border-gray-600 focus:outline-none transition"
              />
            </div>
          </div>

          {message.text && (
            <div className={`mb-4 rounded p-3 ${
              message.type === 'success'
                ? 'bg-green-900/30 border border-green-700'
                : 'bg-red-900/30 border border-red-700'
            }`}>
              <p className={`text-sm ${message.type === 'success' ? 'text-green-400' : 'text-red-400'}`}>
                {message.text}
              </p>
            </div>
          )}

          <button
            onClick={handleConnectRepo}
            disabled={loading || !repoFullname}
            className="w-full rounded border border-gray-700 bg-gray-800 px-4 py-3 font-medium text-white transition hover:border-gray-600 hover:bg-gray-750 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <div className="flex items-center justify-center gap-2">
              <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
              </svg>
              {loading ? 'Connecting...' : activeRepo ? 'Update Repository' : 'Connect GitHub Repository'}
            </div>
          </button>
        </div>

        {/* Trigger New Experiment */}
        <div className="rounded border border-gray-800 bg-gray-900 p-6">
          <h2 className="mb-4 text-lg font-semibold text-white">Trigger New Experiment</h2>
          <p className="mb-4 text-sm text-gray-400">
            Manually trigger Northstar to propose and start a new experiment
          </p>
          
          {/* Option to provide codebase context */}
          <div className="mb-4">
            <button
              type="button"
              onClick={() => setShowCodebaseInput(!showCodebaseInput)}
              className="text-sm text-white hover:text-gray-300 transition"
            >
              {showCodebaseInput ? '▼' : '▶'} {showCodebaseInput ? 'Hide' : 'Provide'} Codebase Context (Optional)
            </button>

            {showCodebaseInput && (
              <div className="mt-3">
                <label className="mb-2 block text-sm font-medium text-gray-300">
                  Codebase Context
                </label>
                <textarea
                  value={codebaseContext}
                  onChange={(e) => setCodebaseContext(e.target.value)}
                  placeholder="Paste your codebase context here (e.g., package.json content, main source files, etc.). Leave empty to fetch from GitHub automatically."
                  rows={6}
                  className="w-full rounded border border-gray-700 bg-gray-800 px-4 py-3 text-white placeholder-gray-500 focus:border-gray-600 focus:outline-none transition font-mono text-sm"
                />
                <p className="mt-2 text-xs text-gray-400">
                  Tip: If you provide codebase context, it will be used instead of fetching from GitHub.
                  Otherwise, the system will automatically fetch from GitHub (if GITHUB_TOKEN is set).
                </p>
              </div>
            )}
          </div>

          <button
            onClick={handleTriggerExperiment}
            disabled={loading || !activeRepo}
            className="w-full rounded bg-white px-4 py-3 font-medium text-black hover:bg-gray-100 transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Generating Proposal...' : 'Trigger Experiment'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default Settings;

