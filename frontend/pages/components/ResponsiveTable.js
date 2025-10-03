import React from 'react';

export default function ResponsiveTable({ headers = [], children, className = "" }) {
  return (
    <div className="overflow-x-auto">
      <div className="min-w-full inline-block align-middle">
        <div className={`overflow-hidden border border-border rounded-xl ${className}`}>
          <table className="min-w-full divide-y divide-border">
            <thead className="bg-surface">
              <tr>
                {headers && headers.length > 0 && headers.map((header, index) => (
                  <th
                    key={index}
                    className="px-3 sm:px-6 py-3 text-left text-xs font-medium text-secondary uppercase tracking-wider"
                  >
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="bg-background divide-y divide-border">
              {children}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export function ResponsiveTableRow({ children, className = "" }) {
  return (
    <tr className={`hover:bg-surface/50 transition-colors ${className}`}>
      {children}
    </tr>
  );
}

export function ResponsiveTableCell({ children, className = "" }) {
  return (
    <td className={`px-3 sm:px-6 py-4 whitespace-nowrap text-sm ${className}`}>
      {children}
    </td>
  );
}