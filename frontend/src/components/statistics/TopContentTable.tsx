interface TopContentTableProps {
  items: Array<{ text: string; votes?: number; earnings?: number }>;
  emptyMessage: string;
  showStats?: boolean;
}

export default function TopContentTable({ items, emptyMessage, showStats = false }: TopContentTableProps) {
  if (items.length === 0) {
    return (
      <div className="text-center py-8 text-quip-teal">
        <p>{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-quip-cream">
          <tr>
            <th
              scope="col"
              className="px-4 py-3 text-left text-xs font-medium text-quip-teal uppercase tracking-wider"
            >
              #
            </th>
            <th
              scope="col"
              className="px-4 py-3 text-left text-xs font-medium text-quip-teal uppercase tracking-wider"
            >
              {showStats ? 'Phrase' : 'Prompt'}
            </th>
            {showStats && (
              <>
                <th
                  scope="col"
                  className="px-4 py-3 text-left text-xs font-medium text-quip-teal uppercase tracking-wider"
                >
                  Votes
                </th>
                <th
                  scope="col"
                  className="px-4 py-3 text-left text-xs font-medium text-quip-teal uppercase tracking-wider"
                >
                  Earnings
                </th>
              </>
            )}
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {items.map((item, index) => (
            <tr key={index} className="hover:bg-quip-cream hover:bg-opacity-30 transition-colors">
              <td className="px-4 py-3 whitespace-nowrap text-sm text-quip-teal">{index + 1}</td>
              <td className="px-4 py-3 text-sm text-quip-navy">{item.text}</td>
              {showStats && (
                <>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-quip-navy">
                    {item.votes ?? 0}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-quip-orange">
                    ${item.earnings ?? 0}
                  </td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
