import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import Head from 'next/head';
import { Mail, Lock, ArrowRight, Calendar } from 'lucide-react';
import api from '../utils/api';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errMsg, setErrMsg] = useState('');
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const handleLogin = async (e) => {
    e.preventDefault();
    setErrMsg('');
    setLoading(true);

    try {
      const response = await api.post('/api/auth/login/', {
        username: email, // Can be email or username
        password
      });

      // Store JWT tokens
      localStorage.setItem('access_token', response.data.access);
      localStorage.setItem('refresh_token', response.data.refresh);

      // Fetch and store user information
      try {
        const userResponse = await api.get('/api/auth/profile/');
        localStorage.setItem('user', JSON.stringify(userResponse.data));
      } catch (userError) {
        console.error('Error fetching user data:', userError);
        // Continue anyway, user data might not be critical for all operations
      }

      router.push('/components/DepartmentConfig');
    } catch (error) {
      if (error.response?.data?.detail) {
        setErrMsg(error.response.data.detail);
      } else if (error.response?.data?.non_field_errors) {
        // Handle non-field errors from Django REST framework
        setErrMsg(error.response.data.non_field_errors[0]);
      } else if (error.response?.status === 401) {
        setErrMsg('Authentication failed. Please check your credentials.');
      } else {
        setErrMsg('An error occurred. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Head>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css" />
      </Head>

      <div className="min-h-screen bg-background text-primary font-sans">
        {/* Background Effects */}
        <div className="fixed inset-0 overflow-hidden pointer-events-none">
          <div className="absolute top-1/4 left-1/4 w-[600px] h-[600px] bg-accent-cyan/10 rounded-full blur-[120px] animate-pulse"></div>
          <div className="absolute bottom-1/4 right-1/4 w-[600px] h-[600px] bg-accent-pink/10 rounded-full blur-[120px] animate-pulse"></div>
        </div>

        <div className="relative z-10 w-full min-h-screen flex justify-center items-center p-4 sm:p-6 lg:p-8">
          <div className="w-full max-w-sm sm:max-w-md">
            {/* Logo */}
            <div className="mb-8 text-center">
              <div className="relative h-16 w-16 mx-auto mb-4">
                <div className="absolute inset-0 bg-gradient-to-r from-accent-cyan to-accent-pink rounded-2xl blur opacity-40"></div>
                <div className="relative bg-surface h-full w-full rounded-2xl flex items-center justify-center border border-border">
                  <Calendar className="h-8 w-8 text-accent-cyan" />
                </div>
              </div>
              <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-gradient-cyan-start to-gradient-pink-end">
                Timetable Generator
              </h1>
              <p className="text-secondary/90 mt-2 font-medium">Sign in to your account</p>
            </div>

            {/* Login Form */}
            <div className="bg-surface/95 backdrop-blur-sm p-6 sm:p-8 rounded-2xl border border-border shadow-soft">
              <form onSubmit={handleLogin} className="space-y-4 sm:space-y-6">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-secondary">Email</label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                      <Mail className="h-4 sm:h-5 w-4 sm:w-5 text-secondary" />
                    </div>
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="w-full pl-9 sm:pl-10 pr-4 py-2.5 sm:py-3 bg-background/95 border border-border rounded-xl text-primary placeholder-secondary/70 focus:outline-none focus:ring-2 focus:ring-accent-cyan/30 focus:border-accent-cyan/30 text-sm sm:text-base"
                      placeholder="Enter your email"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium text-secondary">Password</label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                      <Lock className="h-4 sm:h-5 w-4 sm:w-5 text-secondary" />
                    </div>
                    <input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="w-full pl-9 sm:pl-10 pr-4 py-2.5 sm:py-3 bg-background/95 border border-border rounded-xl text-primary placeholder-secondary/70 focus:outline-none focus:ring-2 focus:ring-accent-cyan/30 focus:border-accent-cyan/30 text-sm sm:text-base"
                      placeholder="Enter your password"
                    />
                  </div>
                </div>

                <div className="flex items-center justify-between">
                  <Link
                    href="/forgot-password"
                    className="text-sm text-accent-cyan hover:text-accent-cyan/80 transition-colors"
                  >
                    Forgot password?
                  </Link>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-2.5 sm:py-3 px-4 bg-gradient-to-r from-gradient-cyan-start to-gradient-pink-end text-white font-medium rounded-xl flex items-center justify-center hover:opacity-90 hover:shadow-lg hover:shadow-accent-cyan/30 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed group text-sm sm:text-base"
                >
                  {loading ? (
                    <div className="h-4 sm:h-5 w-4 sm:w-5 border-2 border-white/20 border-t-white rounded-full animate-spin"></div>
                  ) : (
                    <>
                      Sign In
                      <ArrowRight className="ml-2 h-4 w-4 group-hover:translate-x-1 transition-transform" />
                    </>
                  )}
                </button>

                {errMsg && (
                  <div className="p-3 sm:p-4 bg-red-500/10 border border-red-500/20 rounded-xl">
                    <p className="text-red-500 text-xs sm:text-sm text-center font-medium">{errMsg}</p>
                  </div>
                )}
              </form>

              <div className="mt-4 sm:mt-6 flex flex-col sm:flex-row items-center justify-center gap-2 sm:gap-2 text-xs sm:text-sm">
                <span className="text-secondary">Don't have an account?</span>
                <Link
                  href="/components/Signup"
                  className="text-accent-cyan hover:text-accent-cyan/80 transition-colors font-medium"
                >
                  Sign Up
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
