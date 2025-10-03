import { useState, useEffect } from "react";
import { useRouter } from "next/router";
import api from "../utils/api";
import Head from "next/head";
import Link from "next/link";
import BackButton from "./BackButton";
import ResponsiveLayout from "./ResponsiveLayout";
import Navbar from "./Navbar";
import {
  User,
  Clock,
  Save,
  CheckCircle2,
  X,
  AlertCircle,
  Loader2,
  CalendarClock,
  Info,
  ArrowLeft,
  Calendar,
  AlertTriangle
} from 'lucide-react';

const AddTeacher = () => {
  const router = useRouter();
  const { id } = router.query;
  
  // Form states
  const [name, setName] = useState("");

      const [maxClasses, setMaxClasses] = useState(3);
  // Internal availability state: { day: { periodIndex: mode } }
  const [availabilityState, setAvailabilityState] = useState({});
  const [timetableConfig, setTimetableConfig] = useState(null);
  
  // Separate loading states:
  const [configLoading, setConfigLoading] = useState(true);
  const [teacherLoading, setTeacherLoading] = useState(false);
  const [error, setError] = useState("");
  const [showTooltip, setShowTooltip] = useState("");
  
  // Active mode selector: only "mandatory" (unavailable times)
  const [activeMode, setActiveMode] = useState("mandatory");
  const [formErrors, setFormErrors] = useState({});

  // Helper function to generate time slots from config
  const generateTimeSlots = (config) => {
    if (!config || !config.start_time || !config.class_duration || !config.periods) {
      return {};
    }

    const timeSlots = {};
    const days = config.days || ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'];
    
    days.forEach(day => {
      timeSlots[day] = [];
      let currentTime = new Date(`2000-01-01T${config.start_time}`);
      
      for (let i = 0; i < config.periods.length; i++) {
        const startTimeString = currentTime.toLocaleTimeString('en-US', {
          hour: 'numeric',
          minute: '2-digit',
          hour12: true
        });
        
        // Calculate end time
        const endTime = new Date(currentTime);
        endTime.setMinutes(endTime.getMinutes() + config.class_duration);
        const endTimeString = endTime.toLocaleTimeString('en-US', {
          hour: 'numeric',
          minute: '2-digit',
          hour12: true
        });
        
        // Create time range string
        const timeRangeString = `${startTimeString} - ${endTimeString}`;
        timeSlots[day].push(timeRangeString);
        
        // Add class duration for next iteration
        currentTime.setMinutes(currentTime.getMinutes() + config.class_duration);
      }
    });
    
    return timeSlots;
  };

  // Fetch configuration once on mount.
  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const configRes = await api.get("/api/timetable/schedule-configs/");
        
        if (configRes.data.length > 0) {
          // Get the latest config (highest ID)
          const latestConfig = configRes.data
            .sort((a, b) => b.id - a.id)[0];

          if (latestConfig) {
            setTimetableConfig(latestConfig);
          } else {
            setError("No timetable configuration found. Please complete Department Configuration first.");
          }
        } else {
          setError("No timetable configuration found. Please complete Department Configuration first.");
        }
      } catch (err) {
        if (err.response?.status === 401) {
          return;
        }
        setError("Failed to load configuration.");
      } finally {
        setConfigLoading(false);
      }
    };
    fetchConfig();
  }, []);

  // Fetch teacher data if editing
  useEffect(() => {
    const fetchTeacher = async () => {
      if (!id) return;
      try {
        const { data } = await api.get(`/api/timetable/teachers/${id}/`);
        setName(data.name);
        setMaxClasses(data.max_classes_per_day);
        // Convert availability data to internal state
        const newState = {};
        if (data.unavailable_periods) {
          // Handle only mandatory (unavailable) slots
          const timeSlots = generateTimeSlots(timetableConfig);
          const dayData = data.unavailable_periods['mandatory'] || {};
          for (const [day, times] of Object.entries(dayData)) {
            if (!newState[day]) newState[day] = {};
            times.forEach(time => {
              const periodIndex = timeSlots[day]?.findIndex(p => p === time);
              if (periodIndex !== -1 && periodIndex !== undefined) {
                newState[day][periodIndex] = 'mandatory';
              }
            });
          }
        }
        setAvailabilityState(newState);
      } catch (err) {
        if (err.response?.status === 401) {
          return;
        }
        setError("Failed to load teacher data.");
      }
    };
    if (timetableConfig) {
      fetchTeacher();
    }
  }, [id, timetableConfig]);

  const validateForm = () => {
    const errors = {};
    
    if (!name.trim()) {
      errors.name = "Teacher name is required";
    }
    

    
            if (maxClasses < 1) {
            errors.maxClasses = "Must be at least 1 class per day";
        }
    
    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    
    if (!validateForm()) {
      // Scroll to the top to show errors
      window.scrollTo(0, 0);
      return;
    }
    
    setTeacherLoading(true);

    try {
      const availability = convertAvailability();
      const teacherData = {
        name,
        max_classes_per_day: maxClasses,
        unavailable_periods: { mandatory: availability }
      };

      if (id) {
        await api.put(`/api/timetable/teachers/${id}/`, teacherData);
      } else {
        await api.post("/api/timetable/teachers/", teacherData);
      }
      router.push("/components/Teachers");
    } catch (err) {
      console.log('=== ERROR HANDLING STARTED ===');
      console.error('Error response:', err.response?.data);
      
      // Enhanced error handling for specific duplicate scenarios
      let errorMessage = "Failed to save teacher.";
      
      if (err.response?.data) {
        const errorData = err.response.data;
        
        // Check for field-specific validation errors
        let hasNameError = false;
        let nameMessage = "";
        
        // Check name errors
        if (errorData.name) {
          hasNameError = true;
          if (Array.isArray(errorData.name)) {
            const nameError = errorData.name[0];
            if (typeof nameError === 'object' && nameError.string) {
              nameMessage = nameError.string;
            } else {
              nameMessage = nameError;
            }
          } else {
            nameMessage = errorData.name;
          }
        }
        
        // Determine the specific duplicate scenario
        if (hasNameError) {
          errorMessage = "Teacher name already exists";
        } else if (errorData.detail) {
          // Handle other error types
          if (typeof errorData.detail === 'string') {
            if (errorData.detail.includes('already exists')) {
              errorMessage = "Teacher already exists";
            } else {
              errorMessage = errorData.detail;
            }
          } else {
            errorMessage = errorData.detail;
          }
        } else if (errorData.error) {
          errorMessage = errorData.error;
        }
      }
      
      console.log('Final error message to display:', errorMessage);
      setError(errorMessage);
      window.scrollTo(0, 0);
    } finally {
      setTeacherLoading(false);
    }
  };

  // Combine loading states for rendering:
  const isLoading = configLoading || teacherLoading;



  // Toggle the state for a given day and period index.
  const toggleTimeSlot = (day, periodIndex) => {
    setAvailabilityState(prev => {
      const newState = { ...prev };
      const dayState = newState[day] ? { ...newState[day] } : {};
      if (dayState[periodIndex] === activeMode) {
        // If cell is already set to active mode, remove it.
        delete dayState[periodIndex];
      } else {
        // Otherwise, set cell to active mode.
        dayState[periodIndex] = activeMode;
      }
      newState[day] = dayState;
      return newState;
    });
  };

  // Convert internal availabilityState into final JSON format:
  // { mandatory: { day: [time, ...], ... } }
  const convertAvailability = () => {
    const result = {};
    if (!timetableConfig) return result;
    
    const timeSlots = generateTimeSlots(timetableConfig);
    
    // Then populate the times
    for (const [day, periodsObj] of Object.entries(availabilityState)) {
      for (const [periodIndexStr, cellMode] of Object.entries(periodsObj)) {
        const periodIndex = parseInt(periodIndexStr, 10);
        const dayPeriods = timeSlots[day] || [];
        const time = dayPeriods[periodIndex];
        if (time) {
          if (!result[day]) {
            result[day] = [];
          }
          result[day].push(time);
        }
      }
    }

    return result;
  };

  // Get time slot class based on its status
  const getTimeSlotClass = (day, periodIndex) => {
    const mode = availabilityState[day]?.[periodIndex];
    
    if (!mode) {
      return "bg-background/80 border border-border hover:border-accent-cyan/30";
    }
    
    if (mode === "mandatory") {
      return "bg-red-500/20 border border-red-500/30 text-red-500";
    }
    
    return "bg-background/80 border border-border";
  };

  if (isLoading) {
    return (
      <>
        <Head>
          <title>{id ? "Edit Teacher" : "Add New Teacher"}</title>
        </Head>
        <div className="flex min-h-screen bg-background text-primary font-sans">
          <Navbar number={4} />
          <div className="flex-1 p-8 max-w-7xl mx-auto">
            <div className="flex justify-center items-center h-full">
              <div className="text-center">
                <Loader2 className="h-12 w-12 animate-spin text-accent-cyan mx-auto mb-4" />
                <p className="text-secondary">Loading...</p>
              </div>
            </div>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <Head>
        <title>{id ? "Edit Teacher" : "Add New Teacher"}</title>
      </Head>
      <ResponsiveLayout>
        <div className="mb-8">
          <BackButton href="/components/Teachers" label="Back to Teachers" className="mb-4" />
          <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-gradient-cyan-start to-gradient-pink-end mb-2">
            {id ? "Edit Teacher" : "Add New Teacher"}
          </h1>
          <p className="text-secondary/90">
            {id ? "Update teacher information and availability" : "Create a new teacher and set their availability"}
          </p>
        </div>

          {error && (
            <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl mb-6 flex items-center gap-2">
              <AlertCircle className="h-5 w-5 text-red-500" />
              <p className="text-red-500 text-sm font-medium">{error}</p>
            </div>
          )}
          


          <form onSubmit={handleSubmit} className="space-y-8">
            <div className="bg-surface/95 backdrop-blur-sm p-6 rounded-2xl border border-border shadow-soft">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-primary flex items-center gap-2">
                  <User className="h-5 w-5 text-accent-cyan" />
                  Basic Information
                </h2>
                <div className="relative">
                  <button
                    type="button"
                    className="text-secondary hover:text-primary transition-colors"
                    onMouseEnter={() => setShowTooltip("basic")}
                    onMouseLeave={() => setShowTooltip("")}
                  >
                    <Info className="h-5 w-5" />
                  </button>
                  {showTooltip === "basic" && (
                    <div className="absolute right-0 top-full mt-2 p-3 bg-surface border border-border rounded-xl shadow-lg text-sm text-secondary w-64 z-50">
                      Enter teacher's name and maximum number of classes they can teach per day.
                    </div>
                  )}
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-secondary">Name*</label>
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-secondary/70" />
                    <input
                      type="text"
                      value={name}
                      onChange={(e) => {
                        setName(e.target.value);
                        if (formErrors.name) {
                          setFormErrors({...formErrors, name: undefined});
                        }
                      }}
                      className={`w-full pl-10 pr-4 py-3 bg-background/95 border ${formErrors.name ? 'border-red-500' : 'border-border'} rounded-xl text-primary placeholder-secondary/70 focus:outline-none focus:ring-2 focus:ring-accent-cyan/30 focus:border-accent-cyan/30`}
                      placeholder="Enter teacher name"
                      required
                    />
                  </div>
                  {formErrors.name && (
                    <p className="text-red-500 text-xs mt-1">{formErrors.name}</p>
                  )}
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium text-secondary">Max Classes per Day*</label>
                  <div className="relative">
                    <Clock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-secondary/70" />
                    <input
                      type="number"
                      value={maxClasses}
                      onChange={(e) => {
                          setMaxClasses(Math.max(1, parseInt(e.target.value) || 1));
                          if (formErrors.maxClasses) {
                            setFormErrors({...formErrors, maxClasses: undefined});
                          }
                        }}
                      min="1"
                                              className={`w-full pl-10 pr-4 py-3 bg-background/95 border ${formErrors.maxClasses ? 'border-red-500' : 'border-border'} rounded-xl text-primary placeholder-secondary/70 focus:outline-none focus:ring-2 focus:ring-accent-cyan/30 focus:border-accent-cyan/30`}
                      required
                    />
                  </div>
                                        {formErrors.maxClasses && (
                        <p className="text-red-500 text-xs mt-1">{formErrors.maxClasses}</p>
                      )}
                </div>
              </div>
            </div>



            <div className="bg-surface/95 backdrop-blur-sm p-6 rounded-2xl border border-border shadow-soft">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-primary flex items-center gap-2">
                  <Calendar className="h-5 w-5 text-accent-cyan" />
                  Availability
                </h2>
                <div className="relative">
                  <button
                    type="button"
                    className="text-secondary hover:text-primary transition-colors"
                    onMouseEnter={() => setShowTooltip("availability")}
                    onMouseLeave={() => setShowTooltip("")}
                  >
                    <Info className="h-5 w-5" />
                  </button>
                  {showTooltip === "availability" && (
                    <div className="absolute right-0 top-full mt-2 p-3 bg-surface border border-border rounded-xl shadow-lg text-sm text-secondary w-64 z-50">
                      <p>Define when the teacher is unavailable:</p>
                      <ul className="mt-2 list-disc list-inside space-y-1">
                        <li>Click a time slot to mark it</li>
                        <li><span className="text-red-500">Red</span>: Unavailable times</li>
                      </ul>
                    </div>
                  )}
                </div>
              </div>
              
              <div className="flex items-center gap-4 mb-6">
                <button
                  type="button"
                  onClick={() => setActiveMode("mandatory")}
                  className="px-4 py-2 rounded-xl flex items-center gap-2 transition-colors bg-red-500/20 text-red-500 border border-red-500/30 font-medium"
                >
                  <X className="h-4 w-4" />
                  Unavailable Times
                </button>
              </div>
              
              {timetableConfig ? (
                <div className="space-y-6">
                  {(() => {
                    const timeSlots = generateTimeSlots(timetableConfig);
                    return Object.entries(timeSlots).map(([day, times]) => (
                      <div key={day}>
                        <h3 className="text-md font-medium text-primary mb-3">{day}</h3>
                        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
                          {times.map((time, idx) => (
                            <button
                              key={`${day}-${idx}`}
                              type="button"
                              onClick={() => toggleTimeSlot(day, idx)}
                              className={`py-3 px-4 rounded-lg text-center transition-colors ${getTimeSlotClass(day, idx)}`}
                            >
                              <span className="text-sm">{time}</span>
                            </button>
                          ))}
                        </div>
                      </div>
                    ));
                  })()}
                </div>
              ) : (
                <div className="text-center py-8 text-secondary">
                  <p>No timetable configuration available.</p>
                  <p className="text-sm mt-2">Please complete Department Configuration first.</p>
                </div>
              )}
            </div>

            <div className="flex justify-end">
              <button
                type="submit"
                className="px-6 py-3 bg-gradient-to-r from-gradient-cyan-start to-gradient-pink-end text-white font-medium rounded-xl flex items-center gap-2 hover:opacity-90 hover:shadow-lg hover:shadow-accent-cyan/30 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={teacherLoading}
              >
                {teacherLoading ? (
                  <Loader2 className="h-5 w-5 animate-spin" />
                ) : (
                  <Save className="h-5 w-5" />
                )}
                {id ? "Update Teacher" : "Save Teacher"}
              </button>
            </div>
          </form>
      </ResponsiveLayout>
    </>
  );
};

export default AddTeacher;

