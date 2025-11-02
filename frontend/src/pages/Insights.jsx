const Insights = () => {
  const insights = [
    {
      id: 1,
      title: 'Accessibility Improvements',
      message: 'Accessibility improvements deprioritized after user feedback indicated no significant impact on conversion.',
      date: '2 days ago',
      category: 'learned',
    },
    {
      id: 2,
      title: 'Dark Mode Impact',
      message: 'Dark mode increased retention among Gen Z users by 15% during evening hours.',
      date: '5 days ago',
      category: 'discovery',
    },
    {
      id: 3,
      title: 'Checkout Load Time',
      message: 'Checkout load time strongly correlates with conversion - each 100ms improvement leads to +0.1% conversion.',
      date: '1 week ago',
      category: 'correlation',
    },
    {
      id: 4,
      title: 'Form Field Reduction',
      message: 'Reducing checkout form fields below 5 fields shows diminishing returns - optimal is 4-5 fields.',
      date: '2 weeks ago',
      category: 'optimization',
    },
    {
      id: 5,
      title: 'Trust Badges Placement',
      message: 'Trust badges placed above checkout button perform 30% better than below the button.',
      date: '3 weeks ago',
      category: 'placement',
    },
    {
      id: 6,
      title: 'Mobile vs Desktop',
      message: 'Mobile users show 2x sensitivity to checkout complexity compared to desktop users.',
      date: '1 month ago',
      category: 'segment',
    },
  ];

  const categoryColors = {
    learned: 'bg-yellow-900/30 text-yellow-400 border-yellow-700',
    discovery: 'bg-blue-900/30 text-blue-400 border-blue-700',
    correlation: 'bg-green-900/30 text-green-400 border-green-700',
    optimization: 'bg-purple-900/30 text-purple-400 border-purple-700',
    placement: 'bg-pink-900/30 text-pink-400 border-pink-700',
    segment: 'bg-cyan-900/30 text-cyan-400 border-cyan-700',
  };

  return (
    <div className="min-h-screen bg-[#111827]">
      <div className="mx-auto max-w-6xl px-6 py-8 lg:px-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white">Insights</h1>
          <p className="mt-2 text-gray-400">What Northstar has learned over time</p>
        </div>

        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {insights.map((insight) => (
            <div
              key={insight.id}
              className="rounded border border-gray-800 bg-gray-900 p-6 transition-all hover:border-gray-700"
            >
              <div className="mb-3 flex items-center justify-between">
                <span
                  className={`rounded border px-2 py-1 text-xs font-medium ${categoryColors[insight.category] || categoryColors.learned}`}
                >
                  {insight.category}
                </span>
                <span className="text-xs text-gray-500">{insight.date}</span>
              </div>
              <h3 className="mb-2 text-lg font-semibold text-white">{insight.title}</h3>
              <p className="text-sm leading-relaxed text-gray-300">{insight.message}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default Insights;

