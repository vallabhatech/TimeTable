import React, { useState, useEffect } from 'react';
import Navbar from './Navbar';

export default function ResponsiveLayout({ children, showNavbar = true }) {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  // Check if we're on mobile
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 1024); // lg breakpoint
    };

    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // Close mobile menu when clicking outside or on route change
  useEffect(() => {
    if (isMobileMenuOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
    }

    return () => {
      document.body.style.overflow = 'unset';
    };
  }, [isMobileMenuOpen]);

  const toggleMobileMenu = () => {
    setIsMobileMenuOpen(!isMobileMenuOpen);
  };

  if (!showNavbar) {
    return (
      <div className="min-h-screen bg-background text-primary font-sans">
        {children}
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-primary font-sans flex">
      {/* Navigation */}
      <Navbar 
        isMobile={isMobile}
        isOpen={isMobileMenuOpen}
        onToggle={toggleMobileMenu}
      />
      
      {/* Main Content */}
      <div className={`
        flex-1 min-h-screen
        ${isMobile ? 'w-full' : 'ml-0'}
        transition-all duration-300 ease-in-out
      `}>
        {/* Mobile menu button spacing */}
        {isMobile && (
          <div className="h-16 lg:hidden" />
        )}
        
        {/* Content wrapper with responsive padding */}
        <div className="p-4 sm:p-6 lg:p-8 max-w-full overflow-x-hidden">
          {children}
        </div>
      </div>
    </div>
  );
}