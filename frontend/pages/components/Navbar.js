import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import api from '../utils/api';
import {
  Settings,
  Users,
  BookOpen,
  User,
  Building2,
  Calendar,
  LogOut,
  GraduationCap,
  Menu,
  X
} from 'lucide-react';

const menuItems = [
  { name: "Batches", icon: GraduationCap, path: "/components/Batches" },
  { name: "Subjects", icon: BookOpen, path: "/components/Subjects" },
  { name: "Teachers", icon: User, path: "/components/Teachers" },
  { name: "Classrooms", icon: Building2, path: "/components/Classrooms" },
  { name: "Teacher Assignments", icon: Users, path: "/components/TeacherAssignments" },
  { name: "Department Config", icon: Settings, path: "/components/DepartmentConfig" },
  { name: "Timetable", icon: Calendar, path: "/components/Timetable" }
];

export default function Navbar({ isMobile, isOpen, onToggle }) {
  const router = useRouter();
  const currentPath = router.pathname;
  const [currentUser, setCurrentUser] = useState(null);
  const displayName = currentUser?.first_name || currentUser?.username || 'Account';
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [deleteError, setDeleteError] = useState('');

  const handleLogout = () => {
    try {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('user');
    } catch (_) {}
    router.replace('/components/Login');
  };

  const handleDeleteAccount = () => {
    setDeleteError('');
    setShowDeleteConfirm(true);
  };

  const handleConfirmDelete = async () => {
    try {
      setDeleteLoading(true);
      setDeleteError('');
      await api.delete('/api/auth/profile/');
      handleLogout();
    } catch (e) {
      console.error('Failed to delete account', e);
      setDeleteError('Failed to delete account. Please try again.');
    } finally {
      setDeleteLoading(false);
    }
  };

  useEffect(() => {
    try {
      const stored = localStorage.getItem('user');
      if (stored) {
        setCurrentUser(JSON.parse(stored));
      } else {
        // Attempt to fetch if not in storage
        api.get('/api/auth/profile/')
          .then(res => {
            setCurrentUser(res.data);
            try { localStorage.setItem('user', JSON.stringify(res.data)); } catch(_) {}
          })
          .catch(() => {});
      }
    } catch (_) {}
  }, []);

  // Mobile menu button
  if (isMobile) {
    return (
      <>
        {/* Mobile menu button */}
        <div className="lg:hidden fixed top-0 left-0 right-0 z-50 bg-surface/95 backdrop-blur-sm border-b border-border">
          <div className="flex items-center justify-between p-4">
            <div className="flex items-center gap-3">
              <div className="relative h-8 w-8">
                <div className="absolute inset-0 bg-gradient-to-r from-accent-cyan to-accent-pink rounded-lg blur opacity-40"></div>
                <div className="relative bg-surface h-full w-full rounded-lg flex items-center justify-center border border-border">
                  <Calendar className="h-4 w-4 text-accent-cyan" />
                </div>
              </div>
              <h1 className="text-sm font-bold bg-clip-text text-transparent bg-gradient-to-r from-gradient-cyan-start to-gradient-pink-end">
                Timetable Generator
              </h1>
            </div>
            <button
              onClick={onToggle}
              className="p-2 rounded-lg hover:bg-surface/60 transition-all duration-300 transform hover:scale-110 active:scale-95"
            >
              <div className="relative w-6 h-6">
                <Menu className={`h-6 w-6 absolute transition-all duration-300 ${isOpen ? 'opacity-0 rotate-180' : 'opacity-100 rotate-0'}`} />
                <X className={`h-6 w-6 absolute transition-all duration-300 ${isOpen ? 'opacity-100 rotate-0' : 'opacity-0 -rotate-180'}`} />
              </div>
            </button>
          </div>
        </div>

        {/* Mobile sidebar overlay */}
        <div className={`lg:hidden fixed inset-0 z-40 flex transition-opacity duration-300 ${isOpen ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'}`}>
          {/* Backdrop */}
          <div 
            className={`fixed inset-0 bg-black/50 backdrop-blur-sm transition-opacity duration-300 ${isOpen ? 'opacity-100' : 'opacity-0'}`}
            onClick={onToggle}
          />
          
          {/* Sidebar */}
          <div className={`relative flex flex-col w-80 max-w-[85vw] bg-surface border-r border-border h-full transform transition-transform duration-300 ease-out ${isOpen ? 'translate-x-0' : '-translate-x-full'}`}>
              {/* Header Section */}
              <div className="p-6 flex-shrink-0">
                <div className="mb-6">
                  <div className="relative h-12 w-12 mb-4">
                    <div className="absolute inset-0 bg-gradient-to-r from-accent-cyan to-accent-pink rounded-xl blur opacity-40"></div>
                    <div className="relative bg-surface h-full w-full rounded-xl flex items-center justify-center border border-border">
                      <Calendar className="h-6 w-6 text-accent-cyan" />
                    </div>
                  </div>
                  <h1 className="text-lg font-bold bg-clip-text text-transparent bg-gradient-to-r from-gradient-cyan-start to-gradient-pink-end">
                    Timetable Generator
                  </h1>
                  <p className="text-secondary/90 text-sm font-medium">AI-Powered Scheduling</p>
                </div>
              </div>

              {/* Navigation Section */}
              <div className="flex-1 overflow-y-auto px-6">
                <nav className="space-y-2 pb-4">
                  {menuItems.map((item, index) => {
                    const Icon = item.icon;
                    const isActive = currentPath === item.path;
                    
                    return (
                      <Link
                        key={index}
                        href={item.path}
                        onClick={onToggle}
                        className={`
                          flex items-center gap-3 px-4 py-3 rounded-xl cursor-pointer transition-all duration-300 transform
                          ${isActive 
                            ? 'bg-gradient-to-r from-accent-cyan/10 to-accent-pink/10 text-primary border border-border' 
                            : 'text-secondary hover:text-primary hover:bg-surface/60 hover:scale-105'}
                          ${isOpen ? 'translate-x-0 opacity-100' : 'translate-x-4 opacity-0'}
                        `}
                        style={{
                          transitionDelay: isOpen ? `${index * 50}ms` : '0ms'
                        }}
                      >
                        <Icon className={`h-5 w-5 transition-colors duration-300 ${isActive ? 'text-accent-cyan' : 'text-secondary'}`} />
                        <span className="text-sm font-medium">{item.name}</span>
                        {isActive && (
                          <div className="ml-auto h-2 w-2 rounded-full bg-gradient-to-r from-gradient-cyan-start to-gradient-pink-end animate-pulse"></div>
                        )}
                      </Link>
                    );
                  })}
                </nav>
              </div>

              {/* Account / Logout */}
              <div className="flex-shrink-0 p-4 border-t border-border bg-surface">
                {currentUser && (
                  <div className={`mb-3 px-4 py-2 rounded-lg border border-border text-sm text-secondary ${isOpen ? 'translate-x-0 opacity-100' : 'translate-x-4 opacity-0'}`}>
                    <div className="font-medium text-primary">{displayName}</div>
                    <div className="truncate">{currentUser.email}</div>
                  </div>
                )}
                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={() => {
                      handleDeleteAccount();
                    }}
                    className="px-3 py-2 rounded-lg text-secondary hover:text-red-400 hover:bg-red-500/10 transition-all border border-transparent hover:border-red-500/20"
                  >
                    Delete
                  </button>
                  <button
                    onClick={() => {
                      handleLogout();
                      onToggle();
                    }}
                    className="px-3 py-2 rounded-lg text-secondary hover:text-red-400 hover:bg-red-500/10 transition-all border border-transparent hover:border-red-500/20 flex items-center justify-center gap-2"
                  >
                    <LogOut className="h-5 w-5" />
                    Logout
                  </button>
                </div>
              </div>
            </div>
          </div>
        <DeleteConfirmModal 
          open={showDeleteConfirm}
          onCancel={() => setShowDeleteConfirm(false)}
          onConfirm={handleConfirmDelete}
          loading={deleteLoading}
          error={deleteError}
        />
      </>
    );
  }

  // Desktop sidebar
  return (
    <div className="hidden lg:flex w-[280px] bg-surface border-r border-border flex-col h-screen sticky top-0">
      {/* Header Section - Fixed */}
      <div className="p-6 flex-shrink-0">
        <div className="mb-8">
          <div className="relative h-12 w-12 mb-4">
            <div className="absolute inset-0 bg-gradient-to-r from-accent-cyan to-accent-pink rounded-xl blur opacity-40"></div>
            <div className="relative bg-surface h-full w-full rounded-xl flex items-center justify-center border border-border">
              <Calendar className="h-6 w-6 text-accent-cyan" />
            </div>
          </div>
          <h1 className="text-lg font-bold bg-clip-text text-transparent bg-gradient-to-r from-gradient-cyan-start to-gradient-pink-end">
            Timetable Generator
          </h1>
          <p className="text-secondary/90 text-sm font-medium">AI-Powered Scheduling</p>
        </div>
      </div>

      {/* Navigation Section - Scrollable */}
      <div className="flex-1 overflow-y-auto px-6">
        <nav className="space-y-2 pb-4">
          {menuItems.map((item, index) => {
            const Icon = item.icon;
            const isActive = currentPath === item.path;
            
            return (
              <Link
                key={index}
                href={item.path}
                className={`
                  flex items-center gap-3 px-4 py-3 rounded-xl cursor-pointer transition-all duration-300 transform
                  ${isActive 
                    ? 'bg-gradient-to-r from-accent-cyan/10 to-accent-pink/10 text-primary border border-border shadow-lg shadow-accent-cyan/20' 
                    : 'text-secondary hover:text-primary hover:bg-surface/60 hover:scale-105 hover:shadow-md'}
                `}
              >
                <Icon className={`h-5 w-5 transition-all duration-300 ${isActive ? 'text-accent-cyan scale-110' : 'text-secondary'}`} />
                <span className="text-sm font-medium">{item.name}</span>
                {isActive && (
                  <div className="ml-auto h-2 w-2 rounded-full bg-gradient-to-r from-gradient-cyan-start to-gradient-pink-end animate-pulse"></div>
                )}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Account / Logout - Fixed at Bottom */}
      <div className="flex-shrink-0 p-4 border-t border-border bg-surface">
        {currentUser && (
          <div className="mb-3 px-4 py-2 rounded-lg border border-border text-sm text-secondary">
            <div className="font-medium text-primary">{displayName}</div>
            <div className="truncate">{currentUser.email}</div>
          </div>
        )}
        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={handleDeleteAccount}
            className="px-3 py-2 rounded-lg text-secondary hover:text-red-400 hover:bg-red-500/10 transition-all border border-transparent hover:border-red-500/20"
          >
            Delete
          </button>
          <button
            onClick={handleLogout}
            className="px-3 py-2 rounded-lg text-secondary hover:text-red-400 hover:bg-red-500/10 transition-all border border-transparent hover:border-red-500/20 flex items-center justify-center gap-2 group"
          >
            <LogOut className="h-5 w-5 transition-transform duration-300 group-hover:rotate-12" />
            Logout
          </button>
        </div>
      </div>
    <DeleteConfirmModal 
      open={showDeleteConfirm}
      onCancel={() => setShowDeleteConfirm(false)}
      onConfirm={handleConfirmDelete}
      loading={deleteLoading}
      error={deleteError}
      />
      </div>
  );
}

// Simple confirmation modal
function DeleteConfirmModal({ open, onCancel, onConfirm, loading, error }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onCancel} />
      <div className="relative w-[90%] max-w-sm rounded-xl border border-border bg-surface p-5 shadow-xl">
        <div className="text-base font-semibold text-primary mb-1">Delete account?</div>
        <p className="text-sm text-secondary mb-4">This action is permanent and cannot be undone.</p>
        {error ? (
          <div className="mb-3 text-sm text-red-400">{error}</div>
        ) : null}
        <div className="flex items-center justify-end gap-2">
          <button
            onClick={onCancel}
            disabled={loading}
            className="px-3 py-2 rounded-lg text-secondary hover:text-primary hover:bg-surface/60 transition-all border border-border disabled:opacity-60"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className="px-3 py-2 rounded-lg text-white bg-red-500/90 hover:bg-red-500 transition-all disabled:opacity-60"
          >
            {loading ? 'Deleting…' : 'Delete'}
          </button>
        </div>
      </div>
    </div>
  );
}
