const LogFeed = ({ logs }) => {
  return (
    <div className="rounded border border-gray-800 bg-gray-900 p-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white">Agent Activity</h2>
        <div className="flex items-center gap-2">
          <div className="h-2 w-2 rounded-full bg-green-400 animate-pulse"></div>
          <span className="text-xs text-green-400">Live</span>
        </div>
      </div>

      <div className="space-y-3">
        {logs.map((log, index) => (
          <div
            key={index}
            className="rounded bg-gray-800 p-3"
          >
            <p className="text-sm text-gray-300">{log.message}</p>
            <p className="mt-1 text-xs text-gray-500">{log.timestamp}</p>
          </div>
        ))}
      </div>
    </div>
  );
};

export default LogFeed;

