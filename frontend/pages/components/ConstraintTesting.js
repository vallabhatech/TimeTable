import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import ResponsiveLayout from './ResponsiveLayout';
import ResponsiveCard from './ResponsiveCard';
import BackButton from './BackButton';
import api from '../utils/api';

const ConstraintTesting = () => {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [constraintData, setConstraintData] = useState(null);
  const [selectedConstraint, setSelectedConstraint] = useState(null);
  const [detailedAnalysis, setDetailedAnalysis] = useState(null);
  const [error, setError] = useState('');

  // Constraint definitions with user-friendly names and descriptions
  const constraintTypes = [
    {
      id: 'cross_semester_conflicts',
      name: 'Cross-Semester Conflicts',
      description: 'Teachers cannot be scheduled in multiple semesters at the same time',
      icon: '🔄',
      color: 'bg-red-500'
    },
    {
      id: 'subject_frequency',
      name: 'Subject Frequency',
      description: 'Correct number of classes per week based on credit hours',
      icon: '📊',
      color: 'bg-blue-500'
    },
    {
      id: 'teacher_conflicts',
      name: 'Teacher Conflicts',
      description: 'Teachers cannot be in multiple places at the same time',
      icon: '👨‍🏫',
      color: 'bg-yellow-500'
    },
    {
      id: 'room_conflicts',
      name: 'Room Conflicts',
      description: 'Classrooms cannot be double-booked',
      icon: '🏫',
      color: 'bg-green-500'
    },
    {
      id: 'practical_blocks',
      name: 'Practical Blocks',
      description: '3-hour consecutive blocks for practical subjects',
      icon: '🔬',
      color: 'bg-purple-500'
    },
    {
      id: 'friday_time_limits',
      name: 'Friday Time Limits',
      description: 'Classes must end by 12:00/1:00 PM on Friday',
      icon: '📅',
      color: 'bg-indigo-500'
    },
    {
      id: 'thesis_day_constraint',
      name: 'Thesis Day Constraint',
      description: 'Wednesday exclusive for thesis subjects',
      icon: '📝',
      color: 'bg-pink-500'
    },
    {
      id: 'teacher_assignments',
      name: 'Teacher Assignments',
      description: 'Teachers assigned to correct subjects and sections',
      icon: '📋',
      color: 'bg-teal-500'
    },
    {
      id: 'minimum_daily_classes',
      name: 'Minimum Daily Classes',
      description: 'No day with only practical or only one class',
      icon: '📚',
      color: 'bg-orange-500'
    },
    {
      id: 'compact_scheduling',
      name: 'Compact Scheduling',
      description: 'Classes scheduled without gaps and reasonable end times',
      icon: '⏰',
      color: 'bg-cyan-500'
    },
    {
      id: 'friday_aware_scheduling',
      name: 'Friday-Aware Scheduling',
      description: 'Monday-Thursday scheduling considers Friday constraints',
      icon: '🗓️',
      color: 'bg-emerald-500'
    }
  ];

  useEffect(() => {
    fetchConstraintData();
  }, []);

  const fetchConstraintData = async () => {
    setLoading(true);
    setError('');
    
    try {
      const response = await api.get('/api/timetable/constraint-testing/');
      setConstraintData(response.data);
    } catch (err) {
      if (err.response?.status === 401) {
        return;
      }
      setError(err.response?.data?.error || 'Failed to fetch constraint data');
      console.error('Constraint testing error:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchDetailedAnalysis = async (constraintType) => {
    setLoading(true);
    setError('');
    
    try {
      const response = await api.post('/api/timetable/constraint-testing/', {
        constraint_type: constraintType
      });
      setDetailedAnalysis(response.data.analysis);
      setSelectedConstraint(constraintType);
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to fetch detailed analysis');
      console.error('Detailed analysis error:', err);
    } finally {
      setLoading(false);
    }
  };

  const getConstraintInfo = (constraintId) => {
    return constraintTypes.find(c => c.id === constraintId) || {
      name: constraintId,
      description: 'Unknown constraint',
      icon: '❓',
      color: 'bg-gray-500'
    };
  };

  const getStatusIcon = (status) => {
    return status === 'PASS' ? '✅' : '❌';
  };

  const getStatusColor = (status) => {
    return status === 'PASS' ? 'text-green-400' : 'text-red-400';
  };

  const renderDetailedAnalysis = (constraintType, analysis) => {
    if (!analysis) return null;

    const constraintInfo = getConstraintInfo(constraintType);

    return (
      <div className="space-y-6">
        {/* Summary */}
        <div className="bg-gray-900 rounded-lg p-4">
          <div className="flex items-center gap-4 mb-4">
            <div className={`w-12 h-12 ${constraintInfo.color} rounded-lg flex items-center justify-center text-white text-xl`}>
              {constraintInfo.icon}
            </div>
            <div>
              <h3 className="text-xl font-semibold text-gray-100">{constraintInfo.name}</h3>
              <p className="text-gray-400">{constraintInfo.description}</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="text-center">
              <div className={`text-2xl font-bold ${getStatusColor(analysis.status)}`}>
                {getStatusIcon(analysis.status)} {analysis.status}
              </div>
              <div className="text-sm text-gray-400">Overall Status</div>
            </div>
            <div className="text-center">
              <div className={`text-2xl font-bold ${(analysis.total_violations || analysis.total_conflicts || 0) === 0 ? 'text-green-400' : 'text-red-400'}`}>
                {analysis.total_violations || analysis.total_conflicts || 0}
              </div>
              <div className="text-sm text-gray-400">Total Issues</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-400">
                {(analysis.compliant_subjects?.length || analysis.compliant_assignments?.length || analysis.compliant_entries?.length || analysis.compliant_blocks?.length || analysis.compliant_schedules?.length || analysis.compliant_days?.length || 0)}
              </div>
              <div className="text-sm text-gray-400">Compliant Items</div>
            </div>
          </div>
        </div>

        {/* Violations */}
        {(analysis.violations || analysis.conflicts) && (analysis.violations?.length > 0 || analysis.conflicts?.length > 0) && (
          <div className="bg-red-900/20 border border-red-700 rounded-lg p-4">
            <h4 className="text-lg font-semibold text-red-400 mb-4 flex items-center gap-2">
              <i className="fas fa-exclamation-triangle"></i>
              Violations Found
            </h4>
            <div className="space-y-3 max-h-96 overflow-y-auto">
              {(analysis.violations || analysis.conflicts || []).map((violation, index) => (
                <div key={index} className="bg-gray-800 rounded-lg p-3 border border-red-600">
                  {renderViolationDetails(constraintType, violation)}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Compliant Items */}
        {renderCompliantItems(constraintType, analysis)}

        {/* Raw Data (Collapsible) */}
        <details className="bg-gray-900 rounded-lg p-4">
          <summary className="cursor-pointer text-gray-300 hover:text-gray-100 font-medium">
            View Raw Analysis Data
          </summary>
          <pre className="mt-4 text-sm text-gray-400 bg-gray-800 p-4 rounded-lg overflow-x-auto">
            {JSON.stringify(analysis, null, 2)}
          </pre>
        </details>
      </div>
    );
  };

  const renderViolationDetails = (constraintType, violation) => {
    switch (constraintType) {
      case 'cross_semester_conflicts':
        return (
          <div>
            <div className="font-medium text-red-300 mb-2">
              Teacher: {violation.teacher} - {violation.subject}
            </div>
            <div className="text-sm text-gray-300 grid grid-cols-2 gap-2">
              <div>Class: {violation.class_group}</div>
              <div>Time: {violation.day} Period {violation.period}</div>
              <div className="col-span-2">Schedule: {violation.time}</div>
            </div>
            <div className="mt-2 text-xs text-red-400">
              Conflicts: {violation.conflicts?.join(', ')}
            </div>
          </div>
        );

      case 'subject_frequency':
        return (
          <div>
            <div className="font-medium text-red-300 mb-2">
              {violation.subject_name} ({violation.subject_code}) - {violation.class_group}
            </div>
            <div className="text-sm text-gray-300 grid grid-cols-2 gap-2">
              <div>Expected: {violation.expected_count} classes/week</div>
              <div>Actual: {violation.actual_count} classes/week</div>
              <div>Type: {violation.is_practical ? 'Practical' : 'Theory'}</div>
              <div>Issue: {violation.violation_type}</div>
            </div>
            {violation.schedule_details && (
              <div className="mt-2 text-xs text-gray-400">
                <div className="font-medium mb-1">Current Schedule:</div>
                {violation.schedule_details.map((detail, idx) => (
                  <div key={idx} className="ml-2">
                    {detail.day} P{detail.period} ({detail.time}) - {detail.teacher}
                  </div>
                ))}
              </div>
            )}
          </div>
        );

      case 'teacher_conflicts':
      case 'room_conflicts':
        return (
          <div>
            <div className="font-medium text-red-300 mb-2">
              {constraintType === 'teacher_conflicts' ? 'Teacher' : 'Room'}: {violation.teacher_name || violation.classroom_name}
            </div>
            <div className="text-sm text-gray-300 grid grid-cols-2 gap-2">
              <div>Time: {violation.day} Period {violation.period}</div>
              <div>Conflicts: {violation.conflict_count}</div>
            </div>
            <div className="mt-2 text-xs text-gray-400">
              <div className="font-medium mb-1">Conflicting Assignments:</div>
              {violation.conflicting_assignments?.map((assignment, idx) => (
                <div key={idx} className="ml-2">
                  {assignment.subject} - {assignment.class_group} ({assignment.classroom || assignment.teacher})
                </div>
              ))}
            </div>
          </div>
        );

      case 'practical_blocks':
        return (
          <div>
            <div className="font-medium text-red-300 mb-2">
              {violation.subject_name} - {violation.class_group}
            </div>
            <div className="text-sm text-gray-300 grid grid-cols-2 gap-2">
              <div>Day: {violation.day}</div>
              <div>Issue: {violation.violation_type}</div>
              <div>Block Length: {violation.block_length} periods</div>
              <div>Consecutive: {violation.is_consecutive ? 'Yes' : 'No'}</div>
            </div>
            <div className="mt-2 text-xs text-gray-400">
              Periods: {violation.periods?.join(', ')}
            </div>
          </div>
        );

      default:
        return (
          <div className="text-sm text-gray-300">
            <pre className="whitespace-pre-wrap">{JSON.stringify(violation, null, 2)}</pre>
          </div>
        );
    }
  };

  const renderCompliantItems = (constraintType, analysis) => {
    const compliantData = analysis.compliant_subjects || analysis.compliant_assignments ||
                         analysis.compliant_entries || analysis.compliant_blocks ||
                         analysis.compliant_schedules || analysis.compliant_days || [];

    if (compliantData.length === 0) return null;

    return (
      <div className="bg-green-900/20 border border-green-700 rounded-lg p-4">
        <h4 className="text-lg font-semibold text-green-400 mb-4 flex items-center gap-2">
          <i className="fas fa-check-circle"></i>
          Compliant Items ({compliantData.length})
        </h4>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 max-h-64 overflow-y-auto">
          {compliantData.slice(0, 12).map((item, index) => (
            <div key={index} className="bg-gray-800 rounded-lg p-3 border border-green-600">
              <div className="text-sm text-green-300">
                {renderCompliantItemSummary(constraintType, item)}
              </div>
            </div>
          ))}
        </div>
        {compliantData.length > 12 && (
          <div className="mt-3 text-sm text-gray-400 text-center">
            ... and {compliantData.length - 12} more compliant items
          </div>
        )}
      </div>
    );
  };

  const renderCompliantItemSummary = (constraintType, item) => {
    switch (constraintType) {
      case 'subject_frequency':
        return `${item.subject_name} - ${item.class_group} (${item.actual_count}/${item.expected_count})`;
      case 'teacher_assignments':
        return `${item.teacher} → ${item.subject} (${item.class_group})`;
      case 'practical_blocks':
        return `${item.subject_name} - ${item.class_group} (${item.day})`;
      default:
        return JSON.stringify(item).substring(0, 50) + '...';
    }
  };

  if (loading && !constraintData) {
    return (
      <ResponsiveLayout>
        <div className="flex justify-center items-center h-full">
          <div className="text-center text-purple-400 italic">
            <i className="fas fa-spinner fa-spin text-4xl mb-4"></i>
            <p>Loading constraint analysis...</p>
          </div>
        </div>
      </ResponsiveLayout>
    );
  }

  if (error && !constraintData) {
    return (
      <ResponsiveLayout>
        <h1 className="text-3xl text-gray-50 mb-8">Constraint Testing</h1>
        <div className="bg-red-900/50 text-red-200 p-4 rounded-lg mb-6">
          {error}
        </div>
        <div className="mt-8">
          <BackButton href="/components/Timetable" label="Back to Timetable" />
        </div>
      </ResponsiveLayout>
    );
  }

  return (
    <ResponsiveLayout>
      <div className="mb-8">
        <h1 className="text-3xl text-gray-50 mb-4">Constraint Testing & Validation</h1>
        <p className="text-gray-400 mb-6">
          Comprehensive analysis of all timetable constraints. Click on any constraint to view detailed information.
        </p>
        
        {constraintData && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
            <ResponsiveCard className="p-4">
              <div className="text-2xl font-bold text-purple-400">{constraintData.total_entries}</div>
              <div className="text-sm text-gray-400">Total Schedule Entries</div>
            </ResponsiveCard>
            <ResponsiveCard className="p-4">
              <div className={`text-2xl font-bold ${constraintData.total_violations === 0 ? 'text-green-400' : 'text-red-400'}`}>
                {constraintData.total_violations}
              </div>
              <div className="text-sm text-gray-400">Total Violations</div>
            </ResponsiveCard>
            <ResponsiveCard className="p-4">
              <div className={`text-2xl font-bold ${constraintData.overall_compliance ? 'text-green-400' : 'text-red-400'}`}>
                {constraintData.overall_compliance ? '100%' : 'FAILED'}
              </div>
              <div className="text-sm text-gray-400">Overall Compliance</div>
            </ResponsiveCard>
          </div>
        )}
      </div>

      {/* Constraint Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
          {constraintTypes.map((constraint) => {
            const analysisData = constraintData?.constraint_analysis?.[constraint.id];
            const validationResult = constraintData?.validation_results?.constraint_results?.[constraint.name];
            
            const status = analysisData?.status || validationResult?.status || 'UNKNOWN';
            const violations = analysisData?.total_violations || analysisData?.total_conflicts || validationResult?.violations || 0;
            
            return (
              <div
                key={constraint.id}
                className="bg-gray-800 rounded-lg border border-gray-700 hover:border-purple-500 transition-colors cursor-pointer"
                onClick={() => fetchDetailedAnalysis(constraint.id)}
              >
                <div className="p-6">
                  <div className="flex items-center justify-between mb-4">
                    <div className={`w-12 h-12 ${constraint.color} rounded-lg flex items-center justify-center text-white text-xl`}>
                      {constraint.icon}
                    </div>
                    <div className={`text-2xl ${getStatusColor(status)}`}>
                      {getStatusIcon(status)}
                    </div>
                  </div>
                  
                  <h3 className="text-lg font-semibold text-gray-100 mb-2">
                    {constraint.name}
                  </h3>
                  
                  <p className="text-sm text-gray-400 mb-4">
                    {constraint.description}
                  </p>
                  
                  <div className="flex justify-between items-center">
                    <span className={`text-sm font-medium ${getStatusColor(status)}`}>
                      {status}
                    </span>
                    <span className={`text-sm ${violations > 0 ? 'text-red-400' : 'text-green-400'}`}>
                      {violations} violations
                    </span>
                  </div>
                </div>
              </div>
            );
        })}
      </div>

      {/* Refresh Button */}
      <div className="mb-8">
        <button
          onClick={fetchConstraintData}
          disabled={loading}
          className="px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
        >
          {loading ? (
            <>
              <i className="fas fa-spinner fa-spin"></i>
              Refreshing...
            </>
          ) : (
            <>
              <i className="fas fa-sync-alt"></i>
              Refresh Analysis
            </>
          )}
        </button>
      </div>

        {/* Detailed Analysis Modal/Panel */}
        {selectedConstraint && detailedAnalysis && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
            <div className="bg-gray-800 rounded-lg max-w-6xl w-full max-h-[90vh] overflow-y-auto">
              <div className="p-6 border-b border-gray-700">
                <div className="flex justify-between items-center">
                  <h2 className="text-2xl font-bold text-gray-100">
                    {getConstraintInfo(selectedConstraint).name} - Detailed Analysis
                  </h2>
                  <button
                    onClick={() => {
                      setSelectedConstraint(null);
                      setDetailedAnalysis(null);
                    }}
                    className="text-gray-400 hover:text-gray-200 text-2xl"
                  >
                    ×
                  </button>
                </div>
              </div>
              
              <div className="p-6">
                {renderDetailedAnalysis(selectedConstraint, detailedAnalysis)}
              </div>
            </div>
          </div>
        )}

      {/* Back Button */}
      <div className="mt-8">
        <BackButton href="/components/Timetable" label="Back to Timetable" />
      </div>
    </ResponsiveLayout>
  );
};

export default ConstraintTesting;
