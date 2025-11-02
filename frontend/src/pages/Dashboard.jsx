import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import MetricCard from '../components/MetricCard';
import ExperimentCard from '../components/ExperimentCard';
import LogFeed from '../components/LogFeed';
import { proposalsAPI, experimentsAPI, activityLogsAPI, repositoriesAPI } from '../api';

const Dashboard = () => {
  const navigate = useNavigate();
  const [proposals, setProposals] = useState([
    {
      proposal_id: 1,
      idea_summary: 'Reduce checkout form fields',
      status: 'completed',
      expected_impact: { delta_pct: 0.003, metric: 'Checkout Conversion' },
      rationale: 'Simplified checkout flow by removing optional fields',
      repo_id: 'unassigned',
    },
    {
      proposal_id: 2,
      idea_summary: 'Add trust badges to checkout',
      status: 'approved',
      expected_impact: { delta_pct: 0.002, metric: 'Checkout Conversion' },
      rationale: 'Testing security badges above payment button',
      repo_id: 'unassigned',
    },
    {
      proposal_id: 3,
      idea_summary: 'Optimize mobile checkout layout',
      status: 'approved',
      expected_impact: { delta_pct: 0.005, metric: 'Checkout Conversion' },
      rationale: 'Improve mobile UX for checkout process',
      repo_id: 'unassigned',
    },
    {
      proposal_id: 4,
      idea_summary: 'A/B test payment button color',
      status: 'approved',
      expected_impact: { delta_pct: 0.001, metric: 'Checkout Conversion' },
      rationale: 'Testing green vs blue payment button',
      repo_id: 'unassigned',
    },
  ]);
  const [rawExperiments, setRawExperiments] = useState([
    {
      id: 2,
      proposal_id: 2,
      instruction: 'Add trust badges to checkout',
      status: 'running',
      pr_url: null,
    },
    {
      id: 4,
      proposal_id: 4,
      instruction: 'A/B test payment button color',
      status: 'running',
      pr_url: null,
    },
  ]); // Store raw experiment data
  const [experiments, setExperiments] = useState([
    {
      id: 1,
      title: 'Reduce checkout form fields',
      status: 'completed',
      result: '0.3% improvement',
      description: 'Simplified checkout flow by removing optional fields',
      proposal_id: 1,
    },
    {
      id: 2,
      title: 'Add trust badges to checkout',
      status: 'running',
      result: 'In progress...',
      description: 'Testing security badges above payment button',
      proposal_id: 2,
    },
    {
      id: 3,
      title: 'Optimize mobile checkout layout',
      status: 'approved',
      result: 'Approved',
      description: 'Improve mobile UX for checkout process',
      proposal_id: 3,
    },
    {
      id: 4,
      title: 'A/B test payment button color',
      status: 'running',
      result: 'In progress...',
      description: 'Testing green vs blue payment button',
      proposal_id: 4,
    },
  ]); // Displayed experiments
  const [activityLogs, setActivityLogs] = useState([
    {
      message: 'Analyzing checkout conversion trends...',
      timestamp: 'Just now',
    },
    {
      message: 'Detected +0.3% improvement in conversion rate',
      timestamp: '2 minutes ago',
    },
    {
      message: 'Reviewing experiment results from last week',
      timestamp: '15 minutes ago',
    },
    {
      message: 'Identified potential optimization in checkout flow',
      timestamp: '1 hour ago',
    },
    {
      message: 'Monitoring metric performance across mobile and desktop',
      timestamp: '3 hours ago',
    },
  ]);
  const [repositories, setRepositories] = useState([]);
  const [selectedRepo, setSelectedRepo] = useState(null); // null = all repos
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // Comment out loadData to show demo data
    // loadData();
  }, []);

  useEffect(() => {
    // When repositories, proposals, or selected repo changes, reorganize by repo
    organizeByRepository();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [proposals, rawExperiments, repositories, selectedRepo]);

  const organizeByRepository = () => {
    // Group proposals/experiments by repository
    const grouped = {};
    const repoMap = {};
    
    // Create a map of repo_id to repo info
    repositories.forEach(repo => {
      repoMap[repo.id] = repo;
      if (!grouped[repo.id]) {
        grouped[repo.id] = {
          repo: repo,
          proposals: [],
          experiments: []
        };
      }
    });
    
    // Add "unassigned" group for proposals without repo_id
    grouped['unassigned'] = {
      repo: { repo_fullname: 'Unassigned', owner: '', repo_name: 'Unassigned' },
      proposals: [],
      experiments: []
    };
    
    // Group proposals by repo_id
    proposals.forEach(p => {
      const repoId = p.repo_id || 'unassigned';
      if (!grouped[repoId]) {
        grouped[repoId] = {
          repo: repoMap[repoId] || { repo_fullname: 'Unknown', owner: '', repo_name: 'Unknown' },
          proposals: [],
          experiments: []
        };
      }
      grouped[repoId].proposals.push({
        id: p.proposal_id,
        title: p.idea_summary,
        status: p.status,
        result: p.status === 'completed' 
          ? `${(p.expected_impact?.delta_pct || 0) * 100}% improvement`
          : p.status === 'rejected' 
          ? 'Rejected'
          : p.status === 'approved'
          ? 'Approved'
          : 'Pending',
        description: p.rationale || '',
        proposal_id: p.proposal_id,
      });
    });
    
    // Group experiments by proposal's repo_id
    rawExperiments.forEach(e => {
      // Find the proposal for this experiment
      const proposal = proposals.find(p => p.proposal_id === e.proposal_id);
      const repoId = proposal?.repo_id || 'unassigned';
      if (!grouped[repoId]) {
        grouped[repoId] = {
          repo: { repo_fullname: 'Unknown', owner: '', repo_name: 'Unknown' },
          proposals: [],
          experiments: []
        };
      }
      grouped[repoId].experiments.push({
        id: e.id || e.proposal_id,
        title: e.instruction || 'Experiment',
        status: e.status === 'running' ? 'running' : e.status === 'completed' ? 'completed' : 'running',
        result: e.pr_url 
          ? `PR: ${e.pr_url.split('/').pop()}`
          : 'In progress...',
        description: e.instruction || '',
        proposal_id: e.proposal_id,
      });
    });

    // Update experiments list based on selected repo
    if (selectedRepo === null) {
      // Show all experiments
      setExperiments(Object.values(grouped).flatMap(group => [...group.proposals, ...group.experiments]));
    } else {
      // Show only selected repo's experiments
      const selectedGroup = grouped[selectedRepo] || { proposals: [], experiments: [] };
      setExperiments([...selectedGroup.proposals, ...selectedGroup.experiments]);
    }
  };

  // Commented out to show demo data - uncomment when backend is ready
  // eslint-disable-next-line no-unused-vars
  const loadData = async () => {
    setLoading(true);
    try {
      // Load repositories first
      const reposResult = await repositoriesAPI.list();
      setRepositories(reposResult.repositories || []);
      
      // Load proposals and experiments
      const [proposalsResult, experimentsResult, logsResult] = await Promise.all([
        proposalsAPI.list(),
        experimentsAPI.list(),
        activityLogsAPI.list(10),
      ]);

      // Store raw proposals for organization
      setProposals(proposalsResult.proposals);
      
      // Store raw experiments - will be organized by organizeByRepository useEffect
      setRawExperiments(experimentsResult.experiments);
      
      // Format activity logs - fallback to demo data if no logs
      let formattedLogs = [];

      if (logsResult.logs && logsResult.logs.length > 0) {
        formattedLogs = logsResult.logs.map(log => {
          const date = new Date(log.created_at);
          const now = new Date();
          const diffMs = now - date;
          const diffMins = Math.floor(diffMs / 60000);
          const diffHours = Math.floor(diffMs / 3600000);
          const diffDays = Math.floor(diffMs / 86400000);

          let timestamp;
          if (diffMins < 1) timestamp = 'Just now';
          else if (diffMins < 60) timestamp = `${diffMins} ${diffMins === 1 ? 'minute' : 'minutes'} ago`;
          else if (diffHours < 24) timestamp = `${diffHours} ${diffHours === 1 ? 'hour' : 'hours'} ago`;
          else timestamp = `${diffDays} ${diffDays === 1 ? 'day' : 'days'} ago`;

          return {
            message: log.message,
            timestamp,
          };
        });
      } else {
        // Demo agent activity
        formattedLogs = [
          {
            message: 'Analyzing checkout conversion trends...',
            timestamp: 'Just now',
          },
          {
            message: 'Detected +0.3% improvement in conversion rate',
            timestamp: '2 minutes ago',
          },
          {
            message: 'Reviewing experiment results from last week',
            timestamp: '15 minutes ago',
          },
          {
            message: 'Identified potential optimization in checkout flow',
            timestamp: '1 hour ago',
          },
          {
            message: 'Monitoring metric performance across mobile and desktop',
            timestamp: '3 hours ago',
          },
        ];
      }

      setActivityLogs(formattedLogs);
    } catch (error) {
      console.error('Failed to load data:', error);
      // Show demo data on error
      setActivityLogs([
        {
          message: 'Analyzing checkout conversion trends...',
          timestamp: 'Just now',
        },
        {
          message: 'Detected +0.3% improvement in conversion rate',
          timestamp: '2 minutes ago',
        },
        {
          message: 'Reviewing experiment results from last week',
          timestamp: '15 minutes ago',
        },
        {
          message: 'Identified potential optimization in checkout flow',
          timestamp: '1 hour ago',
        },
        {
          message: 'Monitoring metric performance across mobile and desktop',
          timestamp: '3 hours ago',
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#111827]">
      <div className="mx-auto max-w-7xl px-6 py-8 lg:px-8">
        {/* Hero Metric Panel */}
        <div className="mb-8">
          <MetricCard
            title="Checkout Conversion"
            value="2.4%"
            change={0.3}
            goal="3.0%"
            running={2}
          />
        </div>

        {/* Repository Filter */}
        {repositories.length > 0 && (
          <div className="mb-6 rounded border border-gray-800 bg-gray-900 p-4">
            <label className="mb-2 block text-sm font-medium text-gray-300">Filter by Repository</label>
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => setSelectedRepo(null)}
                className={`px-4 py-2 rounded text-sm font-medium transition ${
                  selectedRepo === null
                    ? 'bg-white text-black hover:bg-gray-100'
                    : 'bg-gray-800 text-gray-300 border border-gray-700 hover:border-gray-600'
                }`}
              >
                All Repositories
              </button>
              {repositories.map((repo) => (
                <button
                  key={repo.id}
                  onClick={() => setSelectedRepo(repo.id)}
                  className={`px-4 py-2 rounded text-sm font-medium transition ${
                    selectedRepo === repo.id
                      ? 'bg-white text-black hover:bg-gray-100'
                      : 'bg-gray-800 text-gray-300 border border-gray-700 hover:border-gray-600'
                  }`}
                >
                  {repo.repo_fullname}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Main Content Grid */}
        <div className="grid gap-6 lg:grid-cols-3">
          {/* Recent Experiments Feed */}
          <div className="lg:col-span-2">
            {loading ? (
              <div className="text-center text-gray-400 py-8">Loading...</div>
            ) : experiments.length === 0 ? (
              <div className="text-center text-gray-400 py-8">
                {selectedRepo 
                  ? `No experiments for this repository. Trigger one from Settings!`
                  : 'No experiments yet. Trigger one from Settings!'}
              </div>
            ) : (
              <div className="grid gap-4 md:grid-cols-2">
                {experiments.map((experiment, index) => (
                  <div
                    key={experiment.id || index}
                    onClick={() => {
                      if (experiment.proposal_id) {
                        navigate(`/experiments/${experiment.proposal_id}`);
                      }
                    }}
                    className="cursor-pointer"
                  >
                    <ExperimentCard {...experiment} />
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Activity Log */}
          <div className="lg:col-span-1">
            <LogFeed logs={activityLogs} />
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;

