const LogFeed = ({ logs }) => {
  return (
    <div className="rounded border border-gray-800 bg-gray-900 p-6">
      <h2 className="mb-4 text-lg font-semibold text-white">Activity Log</h2>

      <div className="space-y-4">
        {logs.map((log, index) => (
          <div
            key={index}
            className="flex items-start gap-3 border-l-2 border-gray-700 pl-4"
          >
            <div className="mt-1 h-2 w-2 rounded-full bg-gray-500"></div>
            <div className="flex-1">
              <p className="text-sm text-white">{log.message}</p>
              <p className="mt-1 text-xs text-gray-400">{log.timestamp}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default LogFeed;

