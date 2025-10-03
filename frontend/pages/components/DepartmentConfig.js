import React, { useState, useEffect } from "react";
import { useRouter } from "next/router";
import ResponsiveLayout from "./ResponsiveLayout";
import ResponsiveCard from "./ResponsiveCard";
import Link from "next/link";
import BackButton from "./BackButton";
import api from "../utils/api";
import { Building2, Clock, Plus, ArrowLeft, ArrowRight, Loader2, Info, Trash2, BookOpen, Users, Edit2, AlertCircle, X, CheckCircle2 } from 'lucide-react';

const DepartmentConfig = () => {
  const router = useRouter();
  const [departmentName, setDepartmentName] = useState("");
  const [numPeriods, setNumPeriods] = useState(0);
  const [startTime, setStartTime] = useState("08:00");
  const [days] = useState(["Mon", "Tue", "Wed", "Thu", "Fri"]);
  const [classDuration, setClassDuration] = useState(60);
  const [periods, setPeriods] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [genLoading, setGenLoading] = useState(false);
  const [genError, setGenError] = useState('');
  const [genSuccess, setGenSuccess] = useState('');
  const [showTooltip, setShowTooltip] = useState("");

  // New states for subject-batch assignment
  const [subjects, setSubjects] = useState([]);
  const [batches, setBatches] = useState([]);

  // New states for existing configurations
  const [existingConfigs, setExistingConfigs] = useState([]);
  const [loadingConfigs, setLoadingConfigs] = useState(true);
  const [editingConfig, setEditingConfig] = useState(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(null);
  const [success, setSuccess] = useState("");

  // Fetch subjects and batches on component mount
  useEffect(() => {
    fetchBatches();
    fetchExistingConfigs();
  }, []);

  const fetchExistingConfigs = async () => {
    try {
      const response = await api.get('/api/timetable/schedule-configs/');
      setExistingConfigs(response.data);
    } catch (error) {
      if (error.response?.status === 401) {
        return;
      }
      console.error('Error fetching existing configs:', error);
      setError('Failed to load existing configurations');
    } finally {
      setLoadingConfigs(false);
    }
  };



  const fetchBatches = async () => {
    try {
      const [batchesRes, subjectsRes] = await Promise.all([
        api.get('/api/timetable/batches/'),
        api.get('/api/timetable/subjects/')
      ]);
      setBatches(batchesRes.data);
      setSubjects(subjectsRes.data);
    } catch (error) {
      if (error.response?.status === 401) {
        // Don't set error for 401, let the interceptor handle redirect
        return;
      }
      console.error('Error fetching data:', error);
      setError('Failed to fetch data');
    }
  };

  // Load existing configuration for editing
  const loadConfigForEditing = (config) => {
    setEditingConfig(config);
    setDepartmentName(config.name);
    setNumPeriods(config.periods.length);
    setStartTime(config.start_time.substring(0, 5)); // Remove seconds
    setClassDuration(config.class_duration);
    
    // Generate periods from the existing config
    const newPeriods = {};
    days.forEach(day => {
      newPeriods[day] = [];
      let dayTime = config.start_time.substring(0, 5);
      for (let i = 0; i < config.periods.length; i++) {
        newPeriods[day].push(formatTimeRange(dayTime, config.class_duration));
        dayTime = incrementTime(dayTime, config.class_duration);
      }
    });
    setPeriods(newPeriods);
  };

  // Prerequisite validation adapted from Constraints page
  const validatePrerequisites = async () => {
    try {
      const [configRes, subjectsRes, teachersRes, classroomsRes, batchesRes, assignmentsRes] = await Promise.all([
        api.get('/api/timetable/schedule-configs/'),
        api.get('/api/timetable/subjects/'),
        api.get('/api/timetable/teachers/'),
        api.get('/api/timetable/classrooms/'),
        api.get('/api/timetable/batches/'),
        api.get('/api/timetable/teacher-assignments/')
      ]);

      const issues = [];

      if (!configRes.data.length || !configRes.data[0].start_time || !configRes.data[0].days?.length || !configRes.data[0].periods?.length) {
        issues.push('⚙️ Department Configuration: Set up working days, periods, and times');
      }

      if (!batchesRes.data.length) {
        issues.push('🎓 Batches: Add at least one batch (class)');
      }

      if (!subjectsRes.data.length) {
        issues.push('📚 Subjects: Add at least one subject');
      } else {
        const subjectsWithoutBatch = subjectsRes.data.filter(s => !s.batch || (typeof s.batch === 'string' && s.batch.trim() === ''));
        if (subjectsWithoutBatch.length > 0) {
          issues.push(`📚 Subjects: ${subjectsWithoutBatch.length} subjects need batch assignment`);
        }
      }

      if (!teachersRes.data.length) {
        issues.push('👨‍🏫 Teachers: Add at least one teacher');
      }

      if (!assignmentsRes.data.length) {
        issues.push('👨‍🏫 Teacher Assignments: Create teacher-subject-section assignments');
      }

      if (!classroomsRes.data.length) {
        issues.push('🏫 Classrooms: Add at least one classroom');
      }

      return issues;
    } catch (error) {
      console.error('Validation error:', error);
      return ['❌ Unable to validate prerequisites. Please check your connection.'];
    }
  };

  const handleTimetableError = (error) => {
    let errorMessage = 'Timetable generation failed. ';
    if (error?.response?.data?.error) {
      const apiError = error.response.data.error;
      if (apiError.includes('No valid schedule configuration found')) {
        errorMessage = '⚠️ Missing Department Configuration: Please set up your schedule (working days, periods, times) before generating timetables.';
      } else if (apiError.includes('Teacher') && apiError.includes('returned more than one')) {
        errorMessage = '⚠️ Duplicate Teacher Found: Remove duplicates in Teachers section.';
      } else if (apiError.includes('Subject') && apiError.includes('returned more than one')) {
        errorMessage = '⚠️ Duplicate Subject Found: Remove duplicates in Subjects section.';
      } else if (apiError.includes('Classroom') && apiError.includes('returned more than one')) {
        errorMessage = '⚠️ Duplicate Classroom Found: Remove duplicates in Classrooms section.';
      } else if (apiError.includes('No subjects found')) {
        errorMessage = '⚠️ No Subjects Added: Add subjects before generating timetables.';
      } else if (apiError.includes('No teachers found')) {
        errorMessage = '⚠️ No Teachers Added: Add teachers before generating timetables.';
      } else if (apiError.includes('No classrooms found')) {
        errorMessage = '⚠️ No Classrooms Added: Add classrooms before generating timetables.';
      } else if (apiError.includes('No class groups found')) {
        errorMessage = '⚠️ No Classes Added: Add class groups before generating timetables.';
      } else if (apiError.includes('batch')) {
        errorMessage = '⚠️ Batch Assignment Issue: Some subjects may not be assigned to batches.';
      } else if (apiError.includes('constraint')) {
        errorMessage = '⚠️ Constraint Conflict: Current data cannot satisfy constraints.';
      } else if (apiError.includes('schedule')) {
        errorMessage = '⚠️ Scheduling Conflict: Check teacher availability, classroom capacity, or time slots.';
      } else {
        errorMessage = `⚠️ Generation Error: ${apiError}`;
      }
    } else if (error?.code === 'NETWORK_ERROR' || error?.message?.includes('Network Error')) {
      errorMessage = '🌐 Network Error: Cannot connect to the server. Ensure backend is running.';
    } else {
      errorMessage = `⚠️ Unexpected Error: ${error?.message || 'Unknown error'}`;
    }
    setGenError(errorMessage);
  };

  const handleCheckPrerequisites = async () => {
    setGenLoading(true);
    setGenError('');
    setGenSuccess('');
    const issues = await validatePrerequisites();
    if (issues.length === 0) {
      setGenSuccess('✅ All prerequisites are met! You can now generate the timetable.');
    } else {
      const issuesList = issues.map(issue => `• ${issue}`).join('\n');
      setGenError(`⚠️ Please fix the following issues before generating timetables:\n\n${issuesList}`);
    }
    setGenLoading(false);
  };

  const handleGenerateTimetable = async () => {
    setGenLoading(true);
    setGenError('');
    setGenSuccess('');
    try {
      const validationIssues = await validatePrerequisites();
      if (validationIssues.length > 0) {
        const issuesList = validationIssues.map(issue => `• ${issue}`).join('\n');
        setGenError(`⚠️ Please fix the following issues before generating timetables:\n\n${issuesList}`);
        setGenLoading(false);
        return;
      }
      const response = await api.post('/api/timetable/generate-timetable/', { constraints: [] });
      if (response.data.message === 'Timetable generated successfully') {
        const entriesCount = response.data.entries_count || 'multiple';
        setGenSuccess(`🎉 Timetable generated successfully! Created ${entriesCount} schedule entries. Redirecting to view timetable...`);
        setTimeout(() => {
          router.push('/components/Timetable');
        }, 2000);
      } else {
        handleTimetableError(new Error('Failed to generate timetable'));
      }
    } catch (error) {
      handleTimetableError(error);
    } finally {
      setGenLoading(false);
    }
  };

  // Clear form and reset to create mode
  const clearForm = () => {
    setEditingConfig(null);
    setDepartmentName("");
    setNumPeriods(0);
    setStartTime("08:00");
    setClassDuration(60);
    setPeriods({});
    setError(null);
    setSuccess("");
  };

  // Delete configuration
  const handleDeleteConfig = async (configId) => {
    try {
      await api.delete(`/api/timetable/schedule-configs/${configId}/`);
      setExistingConfigs(existingConfigs.filter(config => config.id !== configId));
      setSuccess("Configuration deleted successfully!");
      setTimeout(() => setSuccess(''), 3000);
      setShowDeleteConfirm(null);
    } catch (error) {
      setError('Failed to delete configuration');
      console.error('Error deleting config:', error);
      setShowDeleteConfirm(null);
    }
  };

  // Time formatting helpers
  const formatTime = (timeString) => {
    const [hours, minutes] = timeString.split(":").map(Number);
    const period = hours >= 12 ? "PM" : "AM";
    const formattedHours = hours % 12 || 12;
    return `${formattedHours}:${String(minutes).padStart(2, "0")} ${period}`;
  };

  const incrementTime = (time, duration) => {
    let [hours, minutes] = time.split(":").map(Number);
    minutes += duration;
    hours += Math.floor(minutes / 60);
    minutes %= 60;
    hours %= 24;
    return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
  };

  const removePeriod = (day, index) => {
    const newPeriods = { ...periods };
    newPeriods[day].splice(index, 1);
    setPeriods(newPeriods);
  };

  const formatTimeRange = (startTime, duration) => {
    const [hours, minutes] = startTime.split(":").map(Number);
    
    // Calculate end time
    let endHours = hours;
    let endMinutes = minutes + duration;
    
    while (endMinutes >= 60) {
      endHours += 1;
      endMinutes -= 60;
    }
    endHours %= 24;
    
    // Format start time
    const startPeriod = hours >= 12 ? "PM" : "AM";
    const startFormattedHours = hours % 12 || 12;
    const startFormatted = `${startFormattedHours}:${String(minutes).padStart(2, "0")} ${startPeriod}`;
    
    // Format end time
    const endPeriod = endHours >= 12 ? "PM" : "AM";
    const endFormattedHours = endHours % 12 || 12;
    const endFormatted = `${endFormattedHours}:${String(endMinutes).padStart(2, "0")} ${endPeriod}`;
    
    return `${startFormatted} - ${endFormatted}`;
  };

  const addPeriod = (day) => {
    // Find the last period and add a new one after it
    const lastPeriod = periods[day][periods[day].length - 1];
    if (!lastPeriod) {
      // If no periods exist, use the start time
      const newTime = incrementTime(startTime, classDuration);
      setPeriods(prev => ({
        ...prev,
        [day]: [...prev[day], formatTimeRange(newTime, classDuration)]
      }));
      return;
    }

    // Parse the last period time and add class duration
    // Extract the end time from the last period (format: "8:00 AM - 9:00 AM")
    const lastPeriodParts = lastPeriod.split(" - ");
    if (lastPeriodParts.length === 2) {
      const lastEndTime = lastPeriodParts[1]; // "9:00 AM"
      const [lastEndTimePart, lastEndPeriod] = lastEndTime.split(" ");
      const [lastEndHours, lastEndMinutes] = lastEndTimePart.split(":").map(Number);
      
      // Convert to 24-hour format for calculation
      let lastEndHours24 = lastEndHours;
      if (lastEndPeriod === "PM" && lastEndHours !== 12) {
        lastEndHours24 += 12;
      } else if (lastEndPeriod === "AM" && lastEndHours === 12) {
        lastEndHours24 = 0;
      }
      
      // Calculate new start time (same as last end time)
      const newStartTime = `${String(lastEndHours24).padStart(2, "0")}:${String(lastEndMinutes).padStart(2, "0")}`;
      
      setPeriods(prev => ({
        ...prev,
        [day]: [...prev[day], formatTimeRange(newStartTime, classDuration)]
      }));
    }
  };


  const validateConfiguration = () => {
    if (!departmentName.trim()) {
      setError("Department name is required.");
      return false;
    }

    if (numPeriods < 1) {
      setError("Number of periods must be at least 1.");
      return false;
    }
    if (classDuration < 30) {
      setError("Class duration should be at least 30 minutes.");
      return false;
    }
    return true;
  };

  const generatePeriods = () => {
    if (!validateConfiguration()) {
      return;
    }

    if (!numPeriods || !startTime || !classDuration) {
      setError("Please fill all required fields before generating periods.");
      return;
    }

    const newPeriods = {};
    let currentTime = startTime;

    days.forEach(day => {
      newPeriods[day] = [];
      let dayTime = startTime;
      for (let i = 0; i < numPeriods; i++) {
        newPeriods[day].push(formatTimeRange(dayTime, classDuration));
        dayTime = incrementTime(dayTime, classDuration);
      }
    });

    setPeriods(newPeriods);
    setError(null); // Clear any previous errors
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validateConfiguration()) {
      return;
    }
    setLoading(true);
    setError(null);

    if (Object.keys(periods).length === 0) {
      setError("Please generate periods before saving.");
      setLoading(false);
      return;
    }

    try {
      // Convert startTime to HH:mm:ss format
      const formattedStartTime = `${startTime}:00`;

      const payload = {
        name: departmentName,
        days,
        periods: Array.from({length: numPeriods}, (_, i) => (i + 1).toString()),
        start_time: formattedStartTime,
        class_duration: classDuration,
        constraints: {},
        semester: "Fall 2024",
        academic_year: "2024-2025"
      };

      let response;
      if (editingConfig) {
        // Update existing configuration
        response = await api.put(`/api/timetable/schedule-configs/${editingConfig.id}/`, payload);
        setExistingConfigs(existingConfigs.map(config => 
          config.id === editingConfig.id ? response.data : config
        ));
        setSuccess("Configuration updated successfully!");
      } else {
        // Create new configuration
        response = await api.post("/api/timetable/schedule-configs/", payload);
        setExistingConfigs([...existingConfigs, response.data]);
        setSuccess("Configuration created successfully!");
      }

      // Clear form and show success message
      clearForm();
      setTimeout(() => setSuccess(''), 3000);
      
    } catch (error) {
      if (error.response) {
        setError(`Error: ${error.response.data.detail || "Failed to save configuration"}`);
      } else if (error.request) {
        setError("No response from server. Please check your connection.");
      } else {
        setError("An unexpected error occurred. Please try again.");
      }
      console.error("Submission error:", error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <ResponsiveLayout>
      <div className="mb-8">
        <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-gradient-cyan-start to-gradient-pink-end mb-2">
          Department Configuration
        </h1>
        <p className="text-secondary/90">Set up your department's basic information and schedule</p>
      </div>

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl mb-6 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-red-500" />
            <p className="text-red-500 text-sm font-medium">{error}</p>
          </div>
          <button
            onClick={() => setError(null)}
            className="text-red-500 hover:text-red-600 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {success && (
        <div className="p-4 bg-green-500/10 border border-green-500/20 rounded-xl mb-6 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-5 h-5 bg-green-500 rounded-full flex items-center justify-center">
              <div className="w-2 h-2 bg-white rounded-full"></div>
            </div>
            <p className="text-green-500 text-sm font-medium">{success}</p>
          </div>
          <button
            onClick={() => setSuccess('')}
            className="text-green-500 hover:text-green-600 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Generation alerts (prereq/gen) */}
      {(genSuccess || genError) && (
        <div className={`p-4 rounded-xl mb-6 ${genError ? 'bg-red-500/10 border border-red-500/20' : 'bg-green-500/10 border border-green-500/20'}`}>
          <div className="flex items-start gap-3">
            {genError ? (
              <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
            ) : (
              <CheckCircle2 className="h-5 w-5 text-green-500 flex-shrink-0 mt-0.5" />
            )}
            <div className="flex-1 text-sm whitespace-pre-line {genError ? 'text-red-500' : 'text-green-500'}">
              {genError || genSuccess}
            </div>
          </div>
        </div>
      )}

      {/* Current Configurations Section */}
      <ResponsiveCard className="p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-primary flex items-center gap-2">
            <Building2 className="h-5 w-5 text-accent-cyan" />
            Current Department Configurations
          </h2>
          <div className="relative">
            <button
              type="button"
              className="text-secondary hover:text-primary transition-colors"
              onMouseEnter={() => setShowTooltip("current")}
              onMouseLeave={() => setShowTooltip("")}
            >
              <Info className="h-5 w-5" />
            </button>
            {showTooltip === "current" && (
              <div className="absolute right-0 top-full mt-2 p-3 bg-surface border border-border rounded-xl shadow-lg text-sm text-secondary w-64 z-50">
                View and manage your existing department configurations.
              </div>
            )}
          </div>
        </div>

          {loadingConfigs ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-accent-cyan" />
              <span className="ml-2 text-secondary">Loading configurations...</span>
            </div>
          ) : existingConfigs.length === 0 ? (
            <div className="text-center py-8">
              <Building2 className="h-12 w-12 text-secondary/50 mx-auto mb-4" />
              <p className="text-secondary">No department configurations found</p>
              <p className="text-sm text-secondary/70 mt-2">Create your first configuration below</p>
            </div>
          ) : (
            <div className="space-y-4">
              {existingConfigs.map((config) => (
                <div key={config.id} className="bg-background/95 rounded-xl p-4 border border-border">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                         <div className="flex items-center gap-3 mb-2">
                         <h3 className="font-semibold text-white text-lg">{config.name}</h3>
                       </div>
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm text-secondary">
                        <div className="flex items-center gap-2">
                          <Clock className="h-4 w-4 text-accent-cyan" />
                          <span>{config.periods.length} periods</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <Clock className="h-4 w-4 text-accent-cyan" />
                          <span>Starts at {config.start_time.substring(0, 5)}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <Clock className="h-4 w-4 text-accent-cyan" />
                          <span>{config.class_duration} min duration</span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 ml-4">
                      <button
                        onClick={() => loadConfigForEditing(config)}
                        className="p-2 text-secondary hover:text-accent-cyan hover:bg-accent-cyan/10 rounded-lg transition-colors"
                        title="Edit configuration"
                      >
                        <Edit2 className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => setShowDeleteConfirm(config.id)}
                        className="p-2 text-secondary hover:text-red-500 hover:bg-red-500/10 rounded-lg transition-colors"
                        title="Delete configuration"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
      </ResponsiveCard>

        {/* Configuration Form Section */}
        <section className="bg-surface/95 backdrop-blur-sm p-6 rounded-2xl border border-border shadow-soft mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-primary flex items-center gap-2">
              {editingConfig ? (
                <>
                  <Edit2 className="h-5 w-5 text-accent-cyan" />
                  Edit Configuration: {editingConfig.name}
                </>
              ) : (
                <>
                  <Plus className="h-5 w-5 text-accent-cyan" />
                  Create New Configuration
                </>
              )}
            </h2>
            {editingConfig && (
              <button
                onClick={clearForm}
                className="px-4 py-2 text-secondary hover:text-primary border border-border rounded-xl hover:border-accent-cyan/30 transition-colors"
              >
                Cancel Edit
              </button>
            )}
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="bg-surface/95 backdrop-blur-sm p-6 rounded-2xl border border-border shadow-soft">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-md font-semibold text-primary flex items-center gap-2">
                  <Building2 className="h-5 w-5 text-accent-cyan" />
                  Department Information
                </h3>
                <div className="relative">
                  <button
                    type="button"
                    className="text-secondary hover:text-primary transition-colors"
                    onMouseEnter={() => setShowTooltip("department")}
                    onMouseLeave={() => setShowTooltip("")}
                  >
                    <Info className="h-5 w-5" />
                  </button>
                  {showTooltip === "department" && (
                    <div className="absolute right-0 top-full mt-2 p-3 bg-surface border border-border rounded-xl shadow-lg text-sm text-secondary w-64 z-50">
                      Enter your department's name and basic schedule information. This will be used throughout the system.
                    </div>
                  )}
                </div>
              </div>
              <div className="space-y-4">
                <div>
                  <label className="text-sm font-medium text-secondary block mb-2">Department Name</label>
                  <input
                    type="text"
                    value={departmentName}
                    onChange={(e) => setDepartmentName(e.target.value)}
                    className="w-full pl-4 pr-4 py-3 bg-background/95 border border-border rounded-xl text-primary placeholder-secondary/70 focus:outline-none focus:ring-2 focus:ring-accent-cyan/30 focus:border-accent-cyan/30"
                    placeholder="Enter department name"
                    required
                    disabled={loading}
                  />
                </div>
              </div>
            </div>

            <div className="bg-surface/95 backdrop-blur-sm p-6 rounded-2xl border border-border shadow-soft">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-md font-semibold text-primary flex items-center gap-2">
                  <Clock className="h-5 w-5 text-accent-cyan" />
                  Period Configuration
                </h3>
                <div className="relative">
                  <button
                    type="button"
                    className="text-secondary hover:text-primary transition-colors"
                    onMouseEnter={() => setShowTooltip("periods")}
                    onMouseLeave={() => setShowTooltip("")}
                  >
                    <Info className="h-5 w-5" />
                  </button>
                  {showTooltip === "periods" && (
                    <div className="absolute right-0 top-full mt-2 p-3 bg-surface border border-border rounded-xl shadow-lg text-sm text-secondary w-64 z-50">
                      <p className="text-secondary text-sm">
                        Configure your daily schedule. You can customize the timing for each day.
                      </p>
                    </div>
                  )}
                </div>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-secondary">Number of Periods</label>
                  <input
                    type="number"
                    value={numPeriods}
                    onChange={(e) => setNumPeriods(Number(e.target.value))}
                    className="w-full pl-4 pr-4 py-3 bg-background/95 border border-border rounded-xl text-primary placeholder-secondary/70 focus:outline-none focus:ring-2 focus:ring-accent-cyan/30 focus:border-accent-cyan/30"
                    min="1"
                    required
                    disabled={loading}
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium text-secondary">Starting Time</label>
                  <input
                    type="time"
                    value={startTime}
                    onChange={(e) => setStartTime(e.target.value)}
                    className="w-full pl-4 pr-4 py-3 bg-background/95 border border-border rounded-xl text-primary placeholder-secondary/70 focus:outline-none focus:ring-2 focus:ring-accent-cyan/30 focus:border-accent-cyan/30"
                    required
                    disabled={loading}
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium text-secondary">Class Duration (minutes)</label>
                  <input
                    type="number"
                    value={classDuration}
                    onChange={(e) => setClassDuration(Number(e.target.value))}
                    className="w-full pl-4 pr-4 py-3 bg-background/95 border border-border rounded-xl text-primary placeholder-secondary/70 focus:outline-none focus:ring-2 focus:ring-accent-cyan/30 focus:border-accent-cyan/30"
                    min="1"
                    required
                    disabled={loading}
                  />
                </div>

                <div className="flex items-end">
                  <button
                    type="button"
                    onClick={generatePeriods}
                    className="w-full py-3 px-4 bg-gradient-to-r from-gradient-cyan-start to-gradient-pink-end text-white font-medium rounded-xl flex items-center justify-center hover:opacity-90 hover:shadow-lg hover:shadow-accent-cyan/30 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
                    disabled={loading || !numPeriods || !startTime || !classDuration}
                  >
                    {loading ? (
                      <Loader2 className="h-5 w-5 animate-spin" />
                    ) : (
                      "Generate Periods"
                    )}
                  </button>
                </div>
              </div>

              {Object.keys(periods).length > 0 && (
                <div className="mt-6">
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
                    {days.map((day) => (
                      <div key={day} className="bg-background/95 rounded-xl p-4 border border-border">
                        <div className="text-accent-cyan font-medium mb-4">{day}</div>
                        <div className="space-y-2">
                          {periods[day].map((time, i) => (
                            <div
                              key={i}
                              className="group px-3 py-2 bg-surface rounded-lg text-sm text-primary/90 relative hover:bg-surface/80 transition-colors"
                            >
                              <div className="flex items-center justify-between">
                                <span>{time}</span>
                                <div className="opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-2">
                                  <button
                                    type="button"
                                    onClick={() => removePeriod(day, i)}
                                    className="text-secondary hover:text-red-500 transition-colors"
                                    title="Remove this period"
                                  >
                                    <Trash2 className="h-4 w-4" />
                                  </button>
                                </div>
                              </div>
                            </div>
                          ))}
                          <button
                            type="button"
                            className="w-full py-2 border-2 border-dashed border-border text-secondary rounded-lg hover:border-accent-cyan hover:text-accent-cyan transition-colors disabled:opacity-50 group"
                            onClick={() => addPeriod(day)}
                            disabled={loading}
                          >
                            <Plus className="h-4 w-4 mx-auto group-hover:scale-110 transition-transform" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="flex justify-center">
              <button
                type="submit"
                className="px-8 py-3 bg-gradient-to-r from-gradient-cyan-start to-gradient-pink-end text-white font-medium rounded-xl flex items-center gap-2 hover:opacity-90 hover:shadow-lg hover:shadow-accent-cyan/30 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={loading || Object.keys(periods).length === 0}
              >
                {loading ? (
                  <Loader2 className="h-5 w-5 animate-spin" />
                ) : (
                  <>
                    {editingConfig ? <Edit2 className="h-5 w-5" /> : <Plus className="h-5 w-5" />}
                    {editingConfig ? "Update Configuration" : "Save Configuration"}
                  </>
                )}
              </button>
            </div>
          </form>
        </section>

        {/* Batch-Subject Assignment Section */}
        {subjects.length > 0 && (
          <section className="bg-surface/95 backdrop-blur-sm p-6 rounded-2xl border border-border shadow-soft mb-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-primary flex items-center gap-2">
                <BookOpen className="h-5 w-5 text-accent-cyan" />
                Subject-Batch Overview
              </h2>
              <div className="text-sm text-secondary">
                View current subject assignments for each batch
              </div>
            </div>

            {loadingConfigs ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-accent-cyan" />
                <span className="ml-2 text-secondary">Loading data...</span>
              </div>
            ) : (
              <div className="space-y-6">
                {batches.map((batch) => (
                  <div key={batch.name} className="bg-background/95 rounded-xl p-4 border border-border">
                                         <div className="flex items-center gap-2 mb-4">
                       <Users className="h-4 w-4 text-accent-cyan" />
                       <h3 className="font-medium text-white">{batch.name}</h3>
                       <span className="text-sm text-white/90">
                         ({subjects.filter(s => s.batch === batch.name).length} subjects assigned)
                       </span>
                       <span className="text-xs text-white/80">
                         {batch.description} • {batch.total_sections} sections
                       </span>
                     </div>

                    <div className="space-y-4">
                      {/* Show assigned subjects */}
                      <div>
                        <h4 className="text-sm font-medium text-primary mb-3 flex items-center gap-2">
                          <span className="w-2 h-2 bg-accent-cyan rounded-full"></span>
                          Assigned Subjects ({subjects.filter(subject => subject.batch === batch.name).length})
                        </h4>
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                          {subjects
                            .filter(subject => subject.batch === batch.name)
                            .map((subject) => (
                              <div
                                key={subject.id}
                                className="p-3 rounded-lg bg-accent-cyan/10 border border-accent-cyan/30 text-white group hover:bg-accent-cyan/15 transition-all min-w-0 overflow-hidden"
                              >
                                <div className="flex items-start justify-between gap-2">
                                  <div className="flex-1 min-w-0 overflow-hidden">
                                    <div className="font-medium text-sm text-white mb-1 truncate" title={subject.subject_short_name || subject.code}>
                                      {subject.subject_short_name || subject.code}
                                    </div>
                                    <div className="text-xs text-white/90 break-words leading-relaxed overflow-hidden" title={subject.name}>
                                      {subject.name}
                                    </div>
                                  </div>
                                  <div className="flex items-center gap-1 ml-2 flex-shrink-0">
                                    <span className="text-xs text-white/90 whitespace-nowrap">
                                      {subject.credits} cr
                                      {subject.is_practical && (
                                        <span className="ml-1 text-accent-pink font-medium">Lab</span>
                                      )}
                                    </span>
                                  </div>
                                </div>
                              </div>
                            ))}
                        </div>
                        {subjects.filter(subject => subject.batch === batch.name).length === 0 && (
                          <div className="text-sm text-secondary/70 italic p-4 text-center bg-surface/30 rounded-lg border border-dashed border-border">
                            No subjects assigned to this batch yet
                          </div>
                        )}
                      </div>


                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}

        <div className="flex justify-between mt-8">
          <BackButton href="/components/TeacherAssignments" label="Back: Teacher Assignments" />

          <div className="flex gap-3">
            <button
              className="px-6 py-3 border border-accent-cyan/30 text-accent-cyan rounded-xl hover:bg-accent-cyan/10 transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              onClick={handleCheckPrerequisites}
              disabled={genLoading}
            >
              {genLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <CheckCircle2 className="h-4 w-4" />
              )}
              Check Prerequisites
            </button>

            <button
              className="px-6 py-3 bg-gradient-to-r from-gradient-cyan-start to-gradient-pink-end text-white font-medium rounded-xl flex items-center gap-2 hover:opacity-90 hover:shadow-lg hover:shadow-accent-cyan/30 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
              onClick={(e) => {
                e.preventDefault();
                handleGenerateTimetable().catch(err => handleTimetableError(err));
              }}
              disabled={genLoading}
            >
              {genLoading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Generating...
                </>
              ) : (
                <>
                  Generate Timetable
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>
          </div>
        </div>

        {/* Delete Confirmation Dialog */}
        {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-surface p-6 rounded-2xl border border-border shadow-lg max-w-md w-full mx-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-primary">Confirm Delete</h3>
              <button
                onClick={() => setShowDeleteConfirm(null)}
                className="text-secondary hover:text-primary transition-colors"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <p className="text-secondary mb-6">
              Are you sure you want to delete this configuration? This action cannot be undone.
            </p>
            <div className="flex justify-end gap-4">
              <button
                onClick={() => setShowDeleteConfirm(null)}
                className="px-4 py-2 border border-border text-secondary rounded-xl hover:text-primary hover:border-accent-cyan/30 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => handleDeleteConfig(showDeleteConfirm)}
                className="px-4 py-2 bg-red-500 text-white rounded-xl hover:bg-red-600 transition-colors"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
        )}
      </ResponsiveLayout>
  );
};

export default DepartmentConfig;