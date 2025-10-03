import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Head from 'next/head';
import Link from 'next/link';
import { Mail, Lock, User, Calendar, ArrowRight } from 'lucide-react';
import api from '../utils/api';

export default function Signup() {
  const router = useRouter();
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [errMsg, setErrMsg] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {}, []);

  const handleSignUp = async (e) => {
    e.preventDefault();
    setErrMsg('');

    if (password !== confirmPassword) {
      setErrMsg('Passwords do not match.');
      return;
    }

    if (password.length < 6) {
      setErrMsg('Password should be at least 6 characters long.');
      return;
    }

    setLoading(true);

    try {
      const signupData = {
        username,
        first_name: firstName,
        last_name: lastName,
        email,
        password,
        password_confirm: confirmPassword
      };
      
      const response = await api.post('/api/auth/register/', signupData);

      // Clear form on success
      setFirstName('');
      setLastName('');
      setUsername('');
      setEmail('');
      setPassword('');
      setConfirmPassword('');
      setErrMsg('');

      // Automatically redirect to login page
      router.push('/components/Login');

    } catch (error) {
      if (error.response?.data?.email) {
        setErrMsg(error.response.data.email[0]);
      } else if (error.response?.data?.username) {
        setErrMsg(error.response.data.username[0]);
      } else if (error.response?.data?.password) {
        setErrMsg(error.response.data.password[0]);
      } else if (error.response?.data?.detail) {
        setErrMsg(error.response.data.detail);
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
        <link
          rel="stylesheet"
          href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css"
        />
      </Head>

      <div className="min-h-screen bg-background text-primary font-sans">
        {/* Background Effects */}
        <div className="fixed inset-0 overflow-hidden pointer-events-none">
          <div className="absolute top-1/4 left-1/4 w-[600px] h-[600px] bg-accent-cyan/10 rounded-full blur-[120px] animate-pulse"></div>
          <div className="absolute bottom-1/4 right-1/4 w-[600px] h-[600px] bg-accent-pink/10 rounded-full blur-[120px] animate-pulse"></div>
        </div>

        <div className="relative z-10 w-full min-h-screen flex justify-center items-center p-4 sm:p-6 lg:p-8">
          <div className="w-full max-w-lg sm:max-w-xl lg:max-w-2xl">
            {/* Logo */}
            <div className="mb-8 text-center">
              <div className="relative h-16 w-16 mx-auto mb-4">
                <div className="absolute inset-0 bg-gradient-to-r from-accent-cyan to-accent-pink rounded-2xl blur opacity-40"></div>
                <div className="relative bg-surface h-full w-full rounded-2xl flex items-center justify-center border border-border">
                  <Calendar className="h-8 w-8 text-accent-cyan" />
                </div>
              </div>
              <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-gradient-cyan-start to-gradient-pink-end">
                Create Account
              </h1>
              <p className="text-secondary/90 mt-2 font-medium">Sign up to get started</p>
            </div>

            {/* Signup Form */}
            <div className="bg-surface/95 backdrop-blur-sm p-6 sm:p-8 rounded-2xl border border-border shadow-soft">
              <form onSubmit={handleSignUp} className="space-y-4 sm:space-y-6">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6">
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-secondary">First Name</label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <User className="h-4 sm:h-5 w-4 sm:w-5 text-secondary" />
                      </div>
                      <input
                        type="text"
                        value={firstName}
                        onChange={(e) => setFirstName(e.target.value)}
                        className="w-full pl-9 sm:pl-10 pr-4 py-2.5 sm:py-3 bg-background/95 border border-border rounded-xl text-primary placeholder-secondary/70 focus:outline-none focus:ring-2 focus:ring-accent-cyan/30 focus:border-accent-cyan/30 text-sm sm:text-base"
                        placeholder="Enter your first name"
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium text-secondary">Last Name</label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <User className="h-4 sm:h-5 w-4 sm:w-5 text-secondary" />
                      </div>
                      <input
                        type="text"
                        value={lastName}
                        onChange={(e) => setLastName(e.target.value)}
                        className="w-full pl-9 sm:pl-10 pr-4 py-2.5 sm:py-3 bg-background/95 border border-border rounded-xl text-primary placeholder-secondary/70 focus:outline-none focus:ring-2 focus:ring-accent-cyan/30 focus:border-accent-cyan/30 text-sm sm:text-base"
                        placeholder="Enter your last name"
                      />
                    </div>
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium text-secondary">Username</label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                      <User className="h-4 sm:h-5 w-4 sm:w-5 text-secondary" />
                    </div>
                    <input
                      type="text"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      className="w-full pl-9 sm:pl-10 pr-4 py-2.5 sm:py-3 bg-background/95 border border-border rounded-xl text-primary placeholder-secondary/70 focus:outline-none focus:ring-2 focus:ring-accent-cyan/30 focus:border-accent-cyan/30 text-sm sm:text-base"
                      placeholder="Choose a username"
                      required
                    />
                  </div>
                </div>

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

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6">
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

                  <div className="space-y-2">
                    <label className="text-sm font-medium text-secondary">Confirm Password</label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <Lock className="h-4 sm:h-5 w-4 sm:w-5 text-secondary" />
                      </div>
                      <input
                        type="password"
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        className="w-full pl-9 sm:pl-10 pr-4 py-2.5 sm:py-3 bg-background/95 border border-border rounded-xl text-primary placeholder-secondary/70 focus:outline-none focus:ring-2 focus:ring-accent-cyan/30 focus:border-accent-cyan/30 text-sm sm:text-base"
                        placeholder="Confirm your password"
                      />
                    </div>
                  </div>
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
                      Create Account
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
                <span className="text-secondary">Already have an account?</span>
                <Link
                  href="/components/Login"
                  className="text-accent-cyan hover:text-accent-cyan/80 transition-colors font-medium"
                >
                  Sign In
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
