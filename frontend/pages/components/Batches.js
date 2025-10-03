import React, { useState, useEffect } from "react";
import Head from "next/head";
import ResponsiveLayout from "./ResponsiveLayout";
import ResponsiveCard from "./ResponsiveCard";
import api from "../utils/api";
import {
  GraduationCap,
  Plus,
  Edit2,
  Trash2,
  Loader2,
  AlertCircle,
  X,
  Hash,
  Calendar,
  BookOpen,
  Users,
  ArrowLeft,
  Shield
} from 'lucide-react';
import Link from "next/link";

const BatchManagement = () => {
  const [batches, setBatches] = useState([]);
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    semester_number: 1,
    academic_year: "2024-2025",
    total_sections: 1,
    class_advisor: ""
  });
  const [formErrors, setFormErrors] = useState({});
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showDeleteAllConfirm, setShowDeleteAllConfirm] = useState(false);
  const [deleteAllLoading, setDeleteAllLoading] = useState(false);
  const [success, setSuccess] = useState("");
  const [showDeleteOneConfirm, setShowDeleteOneConfirm] = useState(null);
  const [deleteOneLoading, setDeleteOneLoading] = useState(false);
  

  useEffect(() => {
    fetchBatches();
  }, []);

  const fetchBatches = async () => {
    try {
      setLoading(true);
      const { data } = await api.get("/api/timetable/batches/");
      setBatches(data);
      setError("");
    } catch (err) {
      if (err.response?.status === 401) {
        return;
      }
      setError("Failed to load batches");
      console.error("Batches fetch error:", err);
    } finally {
      setLoading(false);
    }
  };

  const validateForm = () => {
    const errors = {};
    
    if (!formData.name.trim()) {
      errors.name = "Batch name is required";
    } else if (!/^\d{2}[A-Z]{2}$/i.test(formData.name)) {
      errors.name = "Batch name must be in format: 2 digits + 2 letters (e.g., 21SW, 22SW, 23SW, 24SW, 25SW, etc.)";
    }
    
    if (!formData.description.trim()) {
      errors.description = "Description is required";
    }
    
    if (formData.semester_number < 1 || formData.semester_number > 8) {
      errors.semester_number = "Semester must be between 1 and 8";
    }
    
    if (!formData.academic_year.trim()) {
      errors.academic_year = "Academic year is required";
    }
    if (!formData.class_advisor.trim()) {
      errors.class_advisor = "Class advisor is required";
    }
    
    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: (name === "semester_number" || name === "total_sections") ? Math.max(1, parseInt(value) || 1) : value
    }));
    
    // Clear specific field error when user starts typing
    if (formErrors[name]) {
      setFormErrors(prev => ({
        ...prev,
        [name]: ""
      }));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    
    if (!validateForm()) {
      return;
    }

    setSubmitting(true);

    try {
      if (editingId) {
        // Update existing batch
        const { data } = await api.put(`/api/timetable/batches/${editingId}/`, formData);
        setBatches(batches.map(batch => 
          batch.id === editingId ? data : batch
        ));
      } else {
        // Create new batch
        const { data } = await api.post("/api/timetable/batches/", formData);
        setBatches([...batches, data]);
      }
      setFormData({ name: "", description: "", semester_number: 1, academic_year: "2024-2025", total_sections: 1, class_advisor: "" });
      setEditingId(null);
      setShowForm(false);
    } catch (err) {
      const errorData = err.response?.data;
      if (errorData) {
        if (errorData.name) {
          setFormErrors(prev => ({ ...prev, name: errorData.name[0] }));
        } else {
          setError("Save failed. Please check your input.");
        }
      } else {
        setError("Network error. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleEdit = (batch) => {
    setFormData({
      name: batch.name,
      description: batch.description,
      semester_number: batch.semester_number,
      academic_year: batch.academic_year,
      total_sections: batch.total_sections || 1,
      class_advisor: batch.class_advisor || ""
    });
    setEditingId(batch.id);
    setShowForm(true);
    setFormErrors({});
  };
  
  const clearForm = () => {
    setFormData({ name: "", description: "", semester_number: 1, academic_year: "2024-2025", total_sections: 1, class_advisor: "" });
    setEditingId(null);
    setFormErrors({});
  };

  const handleDelete = async (id) => {
    setShowDeleteOneConfirm(id);
  };

  const confirmDeleteOne = async () => {
    if (!showDeleteOneConfirm) return;
    try {
      setDeleteOneLoading(true);
      await api.delete(`/api/timetable/batches/${showDeleteOneConfirm}/`);
      setBatches(batches.filter(batch => batch.id !== showDeleteOneConfirm));
      if (editingId === showDeleteOneConfirm) {
        clearForm();
        setShowForm(false);
      }
      setSuccess("Batch deleted successfully");
      setTimeout(() => setSuccess(""), 3000);
    } catch (err) {
      setError("Delete failed - batch might be in use by subjects.");
    } finally {
      setShowDeleteOneConfirm(null);
      setDeleteOneLoading(false);
    }
  };

  const handleDeleteAllBatches = async () => {
    try {
      setDeleteAllLoading(true);
      const response = await api.delete('/api/timetable/data-management/batches/');
      
      if (response.data.success) {
        setBatches([]);
        setError("");
        setShowDeleteAllConfirm(false);
        setSuccess(`Deleted ${response.data.deleted_counts.batches} batches, ${response.data.deleted_counts.teacher_assignments} assignments, ${response.data.deleted_counts.timetable_entries} timetable entries.`);
        setTimeout(() => setSuccess(""), 3000);
      } else {
        setError("Failed to delete all batches");
      }
    } catch (err) {
      setError("Failed to delete all batches");
      console.error("Delete all batches error:", err);
    } finally {
      setDeleteAllLoading(false);
    }
  };

  const filteredBatches = batches;

  return (
    <>
      <Head>
        <title>Batch Management - Timetable System</title>
      </Head>

      <ResponsiveLayout>
        <div className="mb-8">
          <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-gradient-cyan-start to-gradient-pink-end mb-2">
            Batch Management
          </h1>
          <p className="text-secondary/90">Manage academic batches and semesters</p>
        </div>

          {error && (
            <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl mb-6 flex items-center gap-2">
              <AlertCircle className="h-5 w-5 text-red-500" />
              <p className="text-red-500 text-sm font-medium">{error}</p>
            </div>
          )}

          <div className="flex justify-between items-center mb-6">
            <div className="flex gap-3">
              {batches.length > 0 && (
                <button
                  onClick={() => setShowDeleteAllConfirm(true)}
                  className="flex items-center gap-2 px-4 py-2 bg-red-500 text-white font-medium rounded-xl hover:bg-red-600 hover:shadow-lg transition-all duration-300"
                >
                  <Trash2 className="h-5 w-5" />
                  Delete All Batches
                </button>
              )}
            </div>
            <button
              onClick={() => {
                setShowForm(!showForm);
                if (!showForm) {
                  clearForm();
                }
              }}
              className="ml-4 px-6 py-3 bg-gradient-to-r from-gradient-cyan-start to-gradient-pink-end text-white font-medium rounded-xl flex items-center gap-2 hover:opacity-90 hover:shadow-lg hover:shadow-accent-cyan/30 transition-all duration-300"
            >
              {showForm ? <X className="h-5 w-5" /> : <Plus className="h-5 w-5" />}
              {showForm ? "Cancel" : "Add Batch"}
            </button>
          </div>

          {/* Add/Edit Form */}
          {showForm && (
            <div className="mb-8 p-6 bg-card/50 backdrop-blur-sm border border-border rounded-xl">
              <h2 className="text-xl font-semibold text-primary mb-4">
                {editingId ? "Edit Batch" : "Add New Batch"}
              </h2>
              
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Batch Name */}
                  <div>
                    <label className="block text-sm font-medium text-secondary mb-2">
                      Batch Name *
                    </label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <Hash className="h-5 w-5 text-secondary/70" />
                      </div>
                      <input
                        type="text"
                        name="name"
                        value={formData.name}
                        onChange={handleInputChange}
                        placeholder="e.g., 21SW, 22SW"
                        className={`w-full pl-10 pr-4 py-3 bg-background/95 border ${formErrors.name ? 'border-red-500' : 'border-border'} rounded-xl text-primary placeholder-secondary/70 focus:outline-none focus:ring-2 focus:ring-accent-cyan/30`}
                        required
                      />
                    </div>
                    {formErrors.name && (
                      <p className="text-red-500 text-xs mt-1">{formErrors.name}</p>
                    )}
                  </div>

                  {/* Semester Number */}
                  <div>
                    <label className="block text-sm font-medium text-secondary mb-2">
                      Semester Number *
                    </label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <BookOpen className="h-5 w-5 text-secondary/70" />
                      </div>
                      <input
                        type="number"
                        name="semester_number"
                        value={formData.semester_number}
                        onChange={handleInputChange}
                        min="1"
                        max="8"
                        className={`w-full pl-10 pr-4 py-3 bg-background/95 border ${formErrors.semester_number ? 'border-red-500' : 'border-border'} rounded-xl text-primary focus:outline-none focus:ring-2 focus:ring-accent-cyan/30`}
                        required
                      />
                    </div>
                    {formErrors.semester_number && (
                      <p className="text-red-500 text-xs mt-1">{formErrors.semester_number}</p>
                    )}
                  </div>

                  {/* Total Sections */}
                  <div>
                    <label className="block text-sm font-medium text-secondary mb-2">
                      Total Sections *
                    </label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <Users className="h-5 w-5 text-secondary/70" />
                      </div>
                      <input
                        type="number"
                        name="total_sections"
                        value={formData.total_sections}
                        onChange={handleInputChange}
                        min="1"
                        max="5"
                        className={`w-full pl-10 pr-4 py-3 bg-background/95 border ${formErrors.total_sections ? 'border-red-500' : 'border-border'} rounded-xl text-primary focus:outline-none focus:ring-2 focus:ring-accent-cyan/30`}
                        required
                      />
                    </div>
                    <p className="text-xs text-secondary/70 mt-1">Number of sections (e.g., 3 for I, II, III)</p>
                    {formErrors.total_sections && (
                      <p className="text-red-500 text-xs mt-1">{formErrors.total_sections}</p>
                    )}
                  </div>
                </div>

                {/* Description */}
                <div>
                  <label className="block text-sm font-medium text-secondary mb-2">
                    Description *
                  </label>
                  <input
                    type="text"
                    name="description"
                    value={formData.description}
                    onChange={handleInputChange}
                    placeholder="e.g., 8th Semester - Final Year"
                    className={`w-full px-4 py-3 bg-background/95 border ${formErrors.description ? 'border-red-500' : 'border-border'} rounded-xl text-primary placeholder-secondary/70 focus:outline-none focus:ring-2 focus:ring-accent-cyan/30`}
                    required
                  />
                  {formErrors.description && (
                    <p className="text-red-500 text-xs mt-1">{formErrors.description}</p>
                  )}
                </div>

                {/* Academic Year */}
                <div>
                  <label className="block text-sm font-medium text-secondary mb-2">
                    Academic Year *
                  </label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                      <Calendar className="h-5 w-5 text-secondary/70" />
                    </div>
                    <input
                      type="text"
                      name="academic_year"
                      value={formData.academic_year}
                      onChange={handleInputChange}
                      placeholder="e.g., 2024-2025"
                      className={`w-full pl-10 pr-4 py-3 bg-background/95 border ${formErrors.academic_year ? 'border-red-500' : 'border-border'} rounded-xl text-primary placeholder-secondary/70 focus:outline-none focus:ring-2 focus:ring-accent-cyan/30`}
                      required
                    />
                  </div>
                  {formErrors.academic_year && (
                    <p className="text-red-500 text-xs mt-1">{formErrors.academic_year}</p>
                  )}
                </div>
                
                {/* Class Advisor */}
                <div>
                  <label className="block text-sm font-medium text-secondary mb-2">
                    Class Advisor *
                  </label>
                  <input
                    type="text"
                    name="class_advisor"
                    value={formData.class_advisor}
                    onChange={handleInputChange}
                    placeholder="Dr. Qasim Ali (Email: qasim.arain@faculty.muet.edu.pk)"
                    className={`w-full px-4 py-3 bg-background/95 border ${formErrors.class_advisor ? 'border-red-500' : 'border-border'} rounded-xl text-primary placeholder-secondary/70 focus:outline-none focus:ring-2 focus:ring-accent-cyan/30`}
                    required
                  />
                  {formErrors.class_advisor && (
                    <p className="text-red-500 text-xs mt-1">{formErrors.class_advisor}</p>
                  )}
                </div>
                
                <button
                  type="submit"
                  className="w-full py-3 px-4 bg-gradient-to-r from-gradient-cyan-start to-gradient-pink-end text-white font-medium rounded-xl flex items-center justify-center gap-2 hover:opacity-90 hover:shadow-lg hover:shadow-accent-cyan/30 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
                  disabled={submitting}
                >
                  {submitting ? (
                    <Loader2 className="h-5 w-5 animate-spin" />
                  ) : (
                    <>
                      {editingId ? <Edit2 className="h-5 w-5" /> : <Plus className="h-5 w-5" />}
                      {editingId ? "Update Batch" : "Add Batch"}
                    </>
                  )}
                </button>
              </form>
            </div>
          )}

          {/* Batches List */}
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-accent-cyan" />
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filteredBatches.map((batch) => (
                <div key={batch.id} className="p-6 bg-card/50 backdrop-blur-sm border border-border rounded-xl hover:shadow-lg hover:shadow-accent-cyan/10 transition-all duration-300">
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className="p-2 bg-gradient-to-r from-gradient-cyan-start to-gradient-pink-end rounded-lg">
                        <GraduationCap className="h-5 w-5 text-white" />
                      </div>
                      <div>
                        <h3 className="font-semibold text-primary">{batch.name}</h3>
                        <p className="text-sm text-secondary">Semester {batch.semester_number}</p>
                        <p className="text-xs text-secondary/70">{batch.total_sections || 1} Section{(batch.total_sections || 1) > 1 ? 's' : ''}</p>
                      </div>
                    </div>
                    
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleEdit(batch)}
                        className="p-2 text-secondary hover:text-accent-cyan hover:bg-accent-cyan/10 rounded-lg transition-colors"
                      >
                        <Edit2 className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(batch.id)}
                        className="p-2 text-secondary hover:text-red-500 hover:bg-red-500/10 rounded-lg transition-colors"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                  
                  <p className="text-secondary text-sm mb-3">{batch.description}</p>
                  {batch.class_advisor && (
                    <p className="text-sm text-primary mb-1">
                      <span className="text-accent-cyan font-medium">Class Advisor</span>: {batch.class_advisor.split('(')[0].trim()}
                    </p>
                  )}
                  <p className="text-xs text-secondary/70">Academic Year: {batch.academic_year}</p>
                </div>
              ))}
            </div>
          )}

          {batches.length === 0 && !loading && (
            <div className="text-center py-12">
              <GraduationCap className="h-12 w-12 text-secondary/50 mx-auto mb-4" />
              <p className="text-secondary">No batches found</p>
            </div>
          )}

          {/* Navigation */}
          <div className="flex justify-end mt-8">
            <Link href="/components/Subjects">
              <button className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-gradient-cyan-start to-gradient-pink-end text-white font-medium rounded-xl hover:opacity-90 hover:shadow-lg hover:shadow-accent-cyan/30 transition-all duration-300">
                Next: Subjects
                <ArrowLeft className="h-4 w-4 rotate-180" />
              </button>
            </Link>
          </div>

          {/* Delete All Confirmation Modal */}
          {showDeleteAllConfirm && (
            <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
              <div className="bg-surface border border-border rounded-xl p-6 max-w-md mx-4">
                <div className="flex items-center gap-3 mb-4">
                  <Shield className="h-6 w-6 text-red-500" />
                  <h3 className="text-lg font-semibold text-primary">Confirm Delete All Batches</h3>
                </div>
                
                <div className="mb-4 p-3 bg-red-700 border border-yellow-200 rounded-lg">
                  <div className="flex items-center gap-2">
                    <AlertCircle className="h-4 w-4 text-yellow-600" />
                    <span className="text-sm text-white">
                      This will delete ALL batches and related data including teacher assignments and timetable entries. This action cannot be undone!
                    </span>
                  </div>
                </div>
                
                <p className="text-secondary mb-6">
                  Are you sure you want to proceed? This will permanently delete {batches.length} batch(es) and all related data.
                </p>
                
                <div className="flex gap-3">
                  <button
                    onClick={() => setShowDeleteAllConfirm(false)}
                    className="flex-1 py-2 px-4 border border-border rounded-lg text-secondary hover:bg-background transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleDeleteAllBatches}
                    disabled={deleteAllLoading}
                    className="flex-1 py-2 px-4 bg-red-500 hover:bg-red-600 text-white rounded-lg transition-colors disabled:opacity-50"
                  >
                    {deleteAllLoading ? (
                      <div className="flex items-center justify-center gap-2">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Deleting...
                      </div>
                    ) : (
                      "Confirm Delete All"
                    )}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Delete One Confirmation Modal */}
          {showDeleteOneConfirm && (
            <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
              <div className="bg-surface border border-border rounded-xl p-6 max-w-md mx-4">
                <div className="flex items-center gap-3 mb-4">
                  <Shield className="h-6 w-6 text-red-500" />
                  <h3 className="text-lg font-semibold text-primary">Confirm Delete Batch</h3>
                </div>
                <p className="text-secondary mb-6">
                  Are you sure you want to delete this batch? Subjects mapped to this batch may be affected.
                </p>
                <div className="flex gap-3">
                  <button
                    onClick={() => setShowDeleteOneConfirm(null)}
                    className="flex-1 py-2 px-4 border border-border rounded-lg text-secondary hover:bg-background transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={confirmDeleteOne}
                    disabled={deleteOneLoading}
                    className="flex-1 py-2 px-4 bg-red-500 hover:bg-red-600 text-white rounded-lg transition-colors disabled:opacity-50"
                  >
                    {deleteOneLoading ? (
                      <div className="flex items-center justify-center gap-2">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Deleting...
                      </div>
                    ) : (
                      "Confirm Delete"
                    )}
                  </button>
                </div>
              </div>
            </div>
          )}
      </ResponsiveLayout>
    </>
  );
};

export default BatchManagement;