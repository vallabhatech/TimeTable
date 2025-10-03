import React from 'react';

const ResponsiveButton = ({ 
  children, 
  variant = 'primary', 
  size = 'md', 
  className = '', 
  disabled = false,
  loading = false,
  icon: Icon,
  iconPosition = 'left',
  fullWidth = false,
  ...props 
}) => {
  const baseClasses = `
    inline-flex items-center justify-center gap-2 font-medium rounded-xl transition-all duration-300 transform
    focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-background
    disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none
    active:scale-95 hover:scale-105
  `;

  const sizeClasses = {
    sm: 'px-3 py-2 text-sm',
    md: 'px-4 py-3 text-sm',
    lg: 'px-6 py-4 text-base',
    xl: 'px-8 py-5 text-lg'
  };

  const variantClasses = {
    primary: `
      bg-gradient-to-r from-gradient-cyan-start to-gradient-pink-end text-white
      hover:shadow-lg hover:shadow-accent-cyan/30
      focus:ring-accent-cyan/50
      border border-transparent
    `,
    secondary: `
      bg-surface/95 text-primary border border-border
      hover:bg-surface hover:border-accent-cyan/30 hover:text-accent-cyan
      focus:ring-accent-cyan/30
      backdrop-blur-sm
    `,
    success: `
      bg-green-500/10 text-green-600 border border-green-500/20
      hover:bg-green-500/20 hover:border-green-500/40 hover:text-green-700
      focus:ring-green-500/30
    `,
    danger: `
      bg-red-500/10 text-red-600 border border-red-500/20
      hover:bg-red-500/20 hover:border-red-500/40 hover:text-red-700
      focus:ring-red-500/30
    `,
    warning: `
      bg-yellow-500/10 text-yellow-600 border border-yellow-500/20
      hover:bg-yellow-500/20 hover:border-yellow-500/40 hover:text-yellow-700
      focus:ring-yellow-500/30
    `,
    ghost: `
      text-secondary hover:text-primary hover:bg-surface/60
      focus:ring-accent-cyan/30
    `
  };

  const widthClasses = fullWidth ? 'w-full' : '';

  const buttonClasses = `
    ${baseClasses}
    ${sizeClasses[size]}
    ${variantClasses[variant]}
    ${widthClasses}
    ${className}
  `.trim();

  const iconSize = {
    sm: 'h-4 w-4',
    md: 'h-5 w-5',
    lg: 'h-6 w-6',
    xl: 'h-7 w-7'
  }[size];

  return (
    <button
      className={buttonClasses}
      disabled={disabled || loading}
      {...props}
    >
      {loading && (
        <svg className={`${iconSize} animate-spin`} fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
      )}
      
      {!loading && Icon && iconPosition === 'left' && (
        <Icon className={iconSize} />
      )}
      
      {children}
      
      {!loading && Icon && iconPosition === 'right' && (
        <Icon className={iconSize} />
      )}
    </button>
  );
};

export default ResponsiveButton;
