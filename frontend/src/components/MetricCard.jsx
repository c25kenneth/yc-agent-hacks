import { LineChart, Line, ResponsiveContainer, XAxis, YAxis, Tooltip } from 'recharts';

const MetricCard = ({ title, value, change, trend, goal, running }) => {
  const mockData = [
    { day: 'Mon', value: 2.1 },
    { day: 'Tue', value: 2.15 },
    { day: 'Wed', value: 2.2 },
    { day: 'Thu', value: 2.25 },
    { day: 'Fri', value: 2.3 },
    { day: 'Sat', value: 2.35 },
    { day: 'Sun', value: 2.4 },
  ];

  return (
    <div className="rounded border border-gray-800 bg-gray-900 p-6">
      <h2 className="mb-4 text-sm font-medium text-gray-400">{title}</h2>

      <div className="mb-4 flex items-baseline gap-2">
        <div className="text-4xl font-bold text-white">
          {value}
        </div>
        <span className={`text-lg font-semibold ${change >= 0 ? 'text-green-400' : 'text-red-400'}`}>
          {change >= 0 ? '↑' : '↓'} {Math.abs(change)}%
        </span>
      </div>

      <div className="mb-4 h-24">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={mockData}>
            <XAxis dataKey="day" stroke="#6B7280" fontSize={10} />
            <YAxis stroke="#6B7280" fontSize={10} domain={[2.0, 2.5]} />
            <Tooltip
              contentStyle={{
                backgroundColor: '#111827',
                border: '1px solid #374151',
                borderRadius: '4px',
                color: '#fff'
              }}
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke="#10B981"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="flex items-center justify-between text-sm">
        <span className="text-gray-400">
          Goal: <span className="text-white font-medium">{goal}</span>
        </span>
        <span className="text-gray-400">
          {running} {running === 1 ? 'experiment' : 'experiments'} running
        </span>
      </div>
    </div>
  );
};

export default MetricCard;

