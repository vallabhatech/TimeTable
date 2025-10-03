import React from 'react';

export default function ResponsiveCard({ 
  title, 
  children, 
  className = "",
  headerActions = null,
  padding = "default" 
}) {
  const paddingClasses = {
    none: "",
    sm: "p-3 sm:p-4",
    default: "p-4 sm:p-6",
    lg: "p-6 sm:p-8"
  };

  return (
    <div className={`bg-surface border border-border rounded-xl shadow-soft ${paddingClasses[padding]} ${className}`}>
      {title && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4 sm:mb-6">
          <h3 className="text-lg sm:text-xl font-semibold text-primary">{title}</h3>
          {headerActions && (
            <div className="flex flex-col sm:flex-row gap-2 sm:gap-3">
              {headerActions}
            </div>
          )}
        </div>
      )}
      {children}
    </div>
  );
}

export function ResponsiveGrid({ 
  children, 
  cols = { xs: 1, sm: 2, md: 3, lg: 4 },
  gap = "4",
  className = "" 
}) {
  const gridClasses = `grid gap-${gap} ${
    cols.xs ? `grid-cols-${cols.xs}` : 'grid-cols-1'
  } ${
    cols.sm ? `sm:grid-cols-${cols.sm}` : ''
  } ${
    cols.md ? `md:grid-cols-${cols.md}` : ''
  } ${
    cols.lg ? `lg:grid-cols-${cols.lg}` : ''
  } ${
    cols.xl ? `xl:grid-cols-${cols.xl}` : ''
  }`;

  return (
    <div className={`${gridClasses} ${className}`}>
      {children}
    </div>
  );
}