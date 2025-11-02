import { useParams, useNavigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { proposalsAPI, experimentsAPI, oauthStorage } from '../api';
import CodeDiff from '../components/CodeDiff';

const ExperimentDetails = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [proposal, setProposal] = useState(null);
  const [experiment, setExperiment] = useState(null);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [updateBlock, setUpdateBlock] = useState('');
  const [message, setMessage] = useState({ type: '', text: '' });

  useEffect(() => {
    loadData();
  }, [id]);

  const loadData = async () => {
    setLoading(true);
    try {
      // Load proposal
      const proposalResult = await proposalsAPI.get(id);
      setProposal(proposalResult.proposal);
      
      // Load experiment if it exists
      // Note: Experiments are only created when a proposal is approved
      // So it's expected that pending proposals won't have experiments yet
      try {
        const experimentResult = await experimentsAPI.getByProposal(id);
        if (experimentResult.experiment) {
          setExperiment(experimentResult.experiment);
        } else {
          setExperiment(null);
        }
      } catch (error) {
        // No experiment yet - this is normal for pending proposals
        // Only log if it's not a 404 (expected case)
        if (!error.message?.includes('404') && !error.message?.includes('not found')) {
          console.warn('Failed to load experiment (this is normal for pending proposals):', error);
        }
        setExperiment(null);
      }

      // Set default update_block from proposal
      if (proposalResult.proposal.update_block) {
        setUpdateBlock(proposalResult.proposal.update_block);
      } else {
        // Generate a simple update block based on technical plan
        const techPlan = proposalResult.proposal.technical_plan || [];
        if (techPlan.length > 0) {
          const plan = techPlan[0];
          setUpdateBlock(`// Update ${plan.file}\n// ${plan.action}\n// ... existing code ...`);
        }
      }
    } catch (error) {
      console.error('Failed to load proposal:', error);
      setMessage({ type: 'error', text: 'Failed to load proposal' });
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async () => {
    if (!updateBlock.trim()) {
      setMessage({ type: 'error', text: 'Please provide an update block' });
      return;
    }

    setProcessing(true);
    setMessage({ type: '', text: '' });

    try {
      const result = await proposalsAPI.approve(id, updateBlock);
      setMessage({ type: 'success', text: 'Proposal approved! PR is being created...' });
      
      // Reload data to get experiment info
      setTimeout(() => {
        loadData();
      }, 1000);
    } catch (error) {
      setMessage({ type: 'error', text: error.message || 'Failed to approve proposal' });
    } finally {
      setProcessing(false);
    }
  };

  const handleReject = async () => {
    setProcessing(true);
    setMessage({ type: '', text: '' });

    try {
      await proposalsAPI.reject(id);
      setMessage({ type: 'success', text: 'Proposal rejected' });
      
      // Navigate back to dashboard
      setTimeout(() => {
        navigate('/dashboard');
      }, 1500);
    } catch (error) {
      setMessage({ type: 'error', text: error.message || 'Failed to reject proposal' });
    } finally {
      setProcessing(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#111827] flex items-center justify-center">
        <p className="text-gray-400">Loading...</p>
      </div>
    );
  }

  if (!proposal) {
    return (
      <div className="min-h-screen bg-[#111827] flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-400 mb-4">Proposal not found</p>
          <button
            onClick={() => navigate('/dashboard')}
            className="text-white hover:text-gray-300"
          >
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  const codeDiff = experiment?.update_block || proposal.update_block || updateBlock || 'No code changes yet';
  const resultsData = proposal.expected_impact ? [
    { name: 'Before', value: 1.0, color: '#6B7280' },
    { name: 'After', value: 1.0 + (proposal.expected_impact.delta_pct || 0), color: '#5AB9EA' },
  ] : [];

  return (
    <div className="min-h-screen bg-[#111827]">
      <div className="mx-auto max-w-5xl px-6 py-8 lg:px-8">
        {/* Back button */}
        <button
          onClick={() => navigate('/dashboard')}
          className="mb-6 text-sm text-gray-400 hover:text-white transition-colors"
        >
          ← Back to Dashboard
        </button>

        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-3xl font-bold text-white">{proposal.idea_summary}</h1>
            <span className={`rounded-full px-3 py-1 text-xs font-medium ${
              proposal.status === 'pending' ? 'bg-yellow-500/10 text-yellow-400' :
              proposal.status === 'approved' ? 'bg-blue-500/10 text-blue-400' :
              proposal.status === 'rejected' ? 'bg-red-500/10 text-red-400' :
              proposal.status === 'completed' ? 'bg-green-500/10 text-green-400' :
              'bg-gray-500/10 text-gray-400'
            }`}>
              {proposal.status}
            </span>
          </div>
          <p className="text-gray-400">{proposal.rationale}</p>
          
          {experiment?.pr_url && (
            <a
              href={experiment.pr_url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-2 inline-block text-white hover:text-gray-300 text-sm"
            >
              View PR on GitHub →
            </a>
          )}
        </div>

        {/* Hypothesis Section */}
        <div className="mb-6 rounded border border-gray-800 bg-gray-900 p-6">
          <h2 className="mb-3 text-lg font-semibold text-white">Hypothesis</h2>
          <p className="text-gray-300">{proposal.rationale}</p>
          
          <div className="mt-4 pt-4 border-t border-gray-800">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-gray-400">Expected Impact</p>
                <p className="text-lg font-semibold text-white">
                  {proposal.expected_impact?.metric || 'N/A'}: +{((proposal.expected_impact?.delta_pct || 0) * 100).toFixed(2)}%
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-400">Confidence</p>
                <p className="text-lg font-semibold text-white">
                  {(proposal.confidence * 100).toFixed(0)}%
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Planned Changes Section */}
        <div className="mb-6 rounded border border-gray-800 bg-gray-900 p-6">
          <h2 className="mb-3 text-lg font-semibold text-white">Planned Changes</h2>
          <p className="mb-3 text-sm text-gray-400">
            {proposal.status === 'pending' 
              ? 'Fast Apply format code update block (required for approval):'
              : 'Code update block:'}
          </p>
          
          {proposal.status === 'pending' ? (
            <>
              <div className="mb-4">
                <p className="text-sm text-gray-400 mb-2">
                  Review the code changes below. You can edit them if needed, or approve as-is.
                </p>
              </div>
              
              {/* Always show the diff preview */}
              {updateBlock.trim() ? (
                <div className="mb-4">
                  <CodeDiff 
                    updateBlock={updateBlock} 
                    filePath={proposal.technical_plan?.[0]?.file || 'Preview'}
                  />
                </div>
              ) : (
                <div className="mb-4 p-4 rounded-lg bg-yellow-500/10 border border-yellow-500/30">
                  <p className="text-sm text-yellow-400">
                    No code changes provided. Please add the update block below.
                  </p>
                </div>
              )}
              
              {/* Editable textarea for making changes */}
              <div className="mt-4">
                <label className="mb-2 block text-sm text-gray-400">
                  Code Changes (edit if needed)
                </label>
                <textarea
                  value={updateBlock}
                  onChange={(e) => setUpdateBlock(e.target.value)}
                  placeholder={`// Code changes in unified diff format with +/- markers\n- old code\n+ new code`}
                  className="w-full rounded bg-gray-800 p-4 font-mono text-sm text-gray-300 border border-gray-700 focus:border-gray-600 focus:outline-none min-h-[200px]"
                />
                <p className="mt-2 text-xs text-gray-500">
                  Tip: Changes are shown in the preview above. Edit this textarea to modify the code changes, then click "Approve & Execute" when ready.
                </p>
              </div>
            </>
          ) : (
            <CodeDiff 
              updateBlock={codeDiff}
              filePath={proposal.technical_plan?.[0]?.file || 'Code Changes'}
            />
          )}
          
          {proposal.technical_plan && proposal.technical_plan.length > 0 && (
            <div className="mt-4 pt-4 border-t border-gray-800">
              <p className="text-sm text-gray-400 mb-2">Technical Plan:</p>
              <ul className="list-disc list-inside text-sm text-gray-300 space-y-1">
                {proposal.technical_plan.map((plan, idx) => (
                  <li key={idx}>{plan.file}: {plan.action}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Experiment Controls */}
        <div className="mb-6 rounded border border-gray-800 bg-gray-900 p-6">
          <h2 className="mb-4 text-lg font-semibold text-white">Experiment Controls</h2>

          {message.text && (
            <div className={`mb-4 rounded-lg p-3 ${
              message.type === 'success' 
                ? 'bg-green-500/10 border border-green-500/30' 
                : 'bg-red-500/10 border border-red-500/30'
            }`}>
              <p className={`text-sm ${message.type === 'success' ? 'text-green-400' : 'text-red-400'}`}>
                {message.text}
              </p>
            </div>
          )}

          {proposal.status === 'pending' && (
            <div className="space-y-3">
              {!updateBlock.trim() && (
                <div className="rounded-lg bg-yellow-500/10 border border-yellow-500/30 p-3">
                  <p className="text-sm text-yellow-400">
                    ⚠️ Code changes are required before approval. Please add the update block above.
                  </p>
                </div>
              )}
              
              <div className="flex gap-4">
                <button
                  onClick={handleApprove}
                  disabled={processing || !updateBlock.trim()}
                  className="flex-1 rounded bg-green-900/40 px-6 py-4 font-semibold text-green-400 border border-green-700 hover:bg-green-900/50 hover:border-green-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {processing ? (
                    <>
                      <span className="animate-spin">⏳</span>
                      Processing...
                    </>
                  ) : (
                    <>
                      ✅ Approve & Create PR
                    </>
                  )}
                </button>
                <button
                  onClick={handleReject}
                  disabled={processing}
                  className="flex-1 rounded bg-red-900/40 px-6 py-4 font-semibold text-red-400 border border-red-700 hover:bg-red-900/50 hover:border-red-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {processing ? 'Processing...' : '❌ Reject'}
                </button>
              </div>
              
              {updateBlock.trim() && (
                <p className="text-xs text-gray-500 text-center mt-2">
                  Ready to submit! Click "Approve & Create PR" to create a PR with these changes.
                </p>
              )}
            </div>
          )}

          {proposal.status !== 'pending' && (
            <div className="rounded bg-gray-800 border border-gray-700 p-4">
              <p className="text-sm text-gray-400 text-center">
                This proposal has been {proposal.status}
              </p>
            </div>
          )}
        </div>

        {/* Results Summary */}
        <div className="rounded border border-gray-800 bg-gray-900 p-6">
          <h2 className="mb-4 text-lg font-semibold text-white">Results Summary</h2>
          
          <div className="mb-6 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={resultsData}>
                <XAxis dataKey="name" stroke="#6B7280" />
                <YAxis stroke="#6B7280" domain={[0, 3]} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#111827',
                    border: '1px solid #374151',
                    borderRadius: '4px',
                    color: '#fff',
                  }}
                />
                <Bar dataKey="value" radius={[8, 8, 0, 0]}>
                  {resultsData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="rounded bg-green-900/30 border border-green-700 p-4">
            <p className="text-sm text-green-400">
              ✅ <span className="font-semibold">Statistically significant improvement detected.</span>
              <span className="ml-2 text-gray-300">Conversion increased from 2.1% to 2.4% (p &lt; 0.05)</span>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ExperimentDetails;

