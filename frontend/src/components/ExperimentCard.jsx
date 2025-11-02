import { Link } from 'react-router-dom';

const ExperimentCard = ({ id, title, status, result, description }) => {
  const statusConfig = {
    completed: { icon: '✅', color: 'text-green-400', bg: 'bg-green-900/30' },
    running: { icon: '⏳', color: 'text-blue-400', bg: 'bg-blue-900/30' },
    rejected: { icon: '❌', color: 'text-red-400', bg: 'bg-red-900/30' },
  };

  const config = statusConfig[status] || statusConfig.running;

  return (
    <div className="rounded border border-gray-800 bg-gray-900 p-6 transition-all hover:border-gray-700">
      <div className="mb-4 flex items-start justify-between">
        <div className="flex-1">
          <div className="mb-2 flex items-center gap-2">
            <span className="text-xl">{config.icon}</span>
            <span className={`rounded px-2 py-1 text-xs font-medium ${config.color} ${config.bg}`}>
              {status.charAt(0).toUpperCase() + status.slice(1)}
            </span>
          </div>
          <h3 className="mb-2 text-lg font-semibold text-white">{title}</h3>
          <p className="text-sm text-gray-400">{description}</p>
        </div>
      </div>

      <div className="mb-4 flex items-center justify-between">
        <div>
          <span className="text-xs text-gray-400">Result</span>
          <p className="text-sm font-medium text-green-400">{result}</p>
        </div>
      </div>

      <Link
        to={`/experiments/${id}`}
        className="block w-full rounded bg-gray-800 px-4 py-2 text-center text-sm font-medium text-white transition-colors hover:bg-gray-700"
      >
        View Details
      </Link>
    </div>
  );
};

export default ExperimentCard;

