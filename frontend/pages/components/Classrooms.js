import React, { useState, useEffect } from "react";
import Head from "next/head";
import ResponsiveLayout from "./ResponsiveLayout";
import ResponsiveCard from "./ResponsiveCard";
import Link from "next/link";
import BackButton from "./BackButton";
import api from "../utils/api";
import {
  Building2,
  Plus,
  Edit2,
  Trash2,
  Loader2,
  ArrowLeft,
  AlertCircle,
  X,
  Shield
} from 'lucide-react';

const Classrooms = () => {
  const [classrooms, setClassrooms] = useState([]);
  const [formData, setFormData] = useState({
    name: "",
    building: ""
  });
  const [editingId, setEditingId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [showDeleteAllConfirm, setShowDeleteAllConfirm] = useState(false);
  const [deleteAllLoading, setDeleteAllLoading] = useState(false);
  const [success, setSuccess] = useState(null);
  const [showDeleteOneConfirm, setShowDeleteOneConfirm] = useState(null);
  const [deleteOneLoading, setDeleteOneLoading] = useState(false);
  

  useEffect(() => {
    fetchClassrooms();
  }, []);

  const fetchClassrooms = async () => {
    try {
      const response = await api.get('/api/timetable/classrooms/');
      setClassrooms(response.data);
    } catch (error) {
      if (error.response?.status === 401) {
        return;
      }
      setError('Failed to load classrooms');
      console.error('Error fetching classrooms:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const validateForm = () => {
    if (!formData.name.trim()) {
      setError("Classroom name is required");
      return false;
    }
    if (!formData.building.trim()) {
      setError("Building name is required");
      return false;
    }
    return true;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    if (!validateForm()) {
      return;
    }

    try {
      const payload = {
        name: formData.name.trim(),
        building: formData.building.trim()
      };

      if (editingId) {
        const response = await api.put(`/api/timetable/classrooms/${editingId}/`, payload);
        setClassrooms(classrooms.map(room =>
          room.id === editingId ? response.data : room
        ));
      } else {
        const response = await api.post('/api/timetable/classrooms/', payload);
        setClassrooms([...classrooms, response.data]);
      }

      setFormData({ name: "", building: "" });
      setShowForm(false);
      setEditingId(null);
    } catch (error) {
      setError(error.response?.data?.detail || 'Failed to save classroom');
      console.error('Error saving classroom:', error);
    }
  };

  const handleEdit = (classroom) => {
    setFormData({
      name: classroom.name,
      building: classroom.building || ""
    });
    setEditingId(classroom.id);
    setShowForm(true);
  };

  const handleDelete = async (id) => {
    setShowDeleteOneConfirm(id);
  };

  const confirmDeleteOne = async () => {
    if (!showDeleteOneConfirm) return;
    try {
      setDeleteOneLoading(true);
      await api.delete(`/api/timetable/classrooms/${showDeleteOneConfirm}/`);
      setClassrooms(classrooms.filter(room => room.id !== showDeleteOneConfirm));
      setSuccess('Classroom deleted');
      setTimeout(() => setSuccess(null), 2500);
    } catch (error) {
      setError('Failed to delete classroom');
    } finally {
      setShowDeleteOneConfirm(null);
      setDeleteOneLoading(false);
    }
  };

  const handleDeleteAllClassrooms = async () => {
    try {
      setDeleteAllLoading(true);
      const response = await api.delete('/api/timetable/data-management/classrooms/');
      
      if (response.data.success) {
        setClassrooms([]);
        setError(null);
        setShowDeleteAllConfirm(false);
        setSuccess(`Deleted ${response.data.deleted_counts.classrooms} classrooms, ${response.data.deleted_counts.timetable_entries} timetable entries.`);
        setTimeout(() => setSuccess(null), 2500);
      } else {
        setError('Failed to delete all classrooms');
      }
    } catch (err) {
      setError('Failed to delete all classrooms');
      console.error('Delete all classrooms error:', err);
    } finally {
      setDeleteAllLoading(false);
    }
  };

  const filteredClassrooms = classrooms;

  return (
    <>
      <Head>
        <title>Classrooms - MUET Timetable System</title>
      </Head>

      <ResponsiveLayout>
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-gradient-cyan-start to-gradient-pink-end mb-2">Classrooms</h1>
            <p className="text-secondary/90">Manage classrooms and their buildings</p>
          </div>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-xl flex items-center gap-3">
            <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0" />
            <span className="text-red-500">{error}</span>
            <button onClick={() => setError(null)} className="ml-auto text-red-500 hover:text-red-400">
              <X className="h-4 w-4" />
            </button>
          </div>
        )}

        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6">
          <div className="flex gap-3">
            {classrooms.length > 0 && (
              <button
                onClick={() => setShowDeleteAllConfirm(true)}
                className="flex items-center gap-2 px-4 py-2 bg-red-500 text-white font-medium rounded-xl hover:bg-red-600 hover:shadow-lg transition-all duration-300"
              >
                <Trash2 className="h-5 w-5" />
                <span className="hidden sm:inline">Delete All Classrooms</span>
                <span className="sm:hidden">Delete All</span>
              </button>
            )}
          </div>
          <button
            onClick={() => {
              setShowForm(true);
              setEditingId(null);
              setFormData({ name: "", building: "" });
              setError(null);
            }}
            className="px-6 py-3 bg-gradient-to-r from-gradient-cyan-start to-gradient-pink-end text-white font-medium rounded-xl flex items-center gap-2 hover:opacity-90 hover:shadow-lg hover:shadow-accent-cyan/30 transition-all duration-300"
          >
            <Plus className="h-4 w-4" />
            Add Classroom
          </button>
        </div>

        {showForm && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-surface rounded-2xl p-6 w-full max-w-md">
              <h2 className="text-xl font-semibold text-primary mb-4">
                {editingId ? 'Edit Classroom' : 'Add New Classroom'}
              </h2>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-secondary mb-2">
                    Classroom Name *
                  </label>
                  <input
                    type="text"
                    name="name"
                    value={formData.name}
                    onChange={handleInputChange}
                    placeholder="e.g., C.R. 01"
                    className="w-full px-4 py-3 bg-background/95 border border-border rounded-xl text-primary placeholder-secondary/70 focus:outline-none focus:ring-2 focus:ring-accent-cyan/30"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-secondary mb-2">
                    Building *
                  </label>
                  <input
                    type="text"
                    name="building"
                    value={formData.building}
                    onChange={handleInputChange}
                    placeholder="e.g., Main Building, Block A"
                    className="w-full px-4 py-3 bg-background/95 border border-border rounded-xl text-primary placeholder-secondary/70 focus:outline-none focus:ring-2 focus:ring-accent-cyan/30"
                    required
                  />
                </div>

                <div className="flex gap-3 pt-4">
                  <button
                    type="button"
                    onClick={() => {
                      setShowForm(false);
                      setEditingId(null);
                      setFormData({ name: "", building: "" });
                      setError(null);
                    }}
                    className="flex-1 px-4 py-3 bg-background/95 hover:bg-surface text-secondary hover:text-primary rounded-xl border border-border transition-all"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-6 py-3 bg-gradient-to-r from-gradient-cyan-start to-gradient-pink-end text-white font-medium rounded-xl flex items-center gap-2 hover:opacity-90 hover:shadow-lg hover:shadow-accent-cyan/30 transition-all duration-300"
                  >
                    {editingId ? 'Update' : 'Add'} Classroom
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-accent-cyan" />
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6">
            {filteredClassrooms.map((classroom) => (
              <ResponsiveCard key={classroom.id} className="p-4 sm:p-6">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-accent-cyan/10 rounded-lg">
                      <Building2 className="h-5 w-5 text-accent-cyan" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-primary">{classroom.name}</h3>
                      <p className="text-sm text-secondary">{classroom.building}</p>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleEdit(classroom)}
                      className="p-2 text-secondary hover:text-accent-cyan transition-colors"
                      title="Edit classroom"
                    >
                      <Edit2 className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => handleDelete(classroom.id)}
                      className="p-2 text-secondary hover:text-red-500 transition-colors"
                      title="Delete classroom"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              </ResponsiveCard>
            ))}

            {classrooms.length === 0 && !loading && (
              <div className="col-span-full text-center py-12">
                <Building2 className="h-12 w-12 text-secondary/50 mx-auto mb-4" />
                <p className="text-secondary">No classrooms added yet.</p>
              </div>
            )}
          </div>
        )}

        {/* Navigation */}
        <div className="flex flex-col sm:flex-row justify-between gap-4 mt-8">
          <BackButton href="/components/Teachers" label="Back: Teachers" />
          <Link href="/components/TeacherAssignments">
            <button className="px-6 py-3 bg-gradient-to-r from-gradient-cyan-start to-gradient-pink-end text-white font-medium rounded-xl flex items-center gap-2 hover:opacity-90 hover:shadow-lg hover:shadow-accent-cyan/30 transition-all duration-300">
              Next: Teacher Assignments
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
                <h3 className="text-lg font-semibold text-primary">Confirm Delete All Classrooms</h3>
              </div>
              
              <div className="mb-4 p-3 bg-red-700 border border-yellow-200 rounded-lg">
                <div className="flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 text-yellow-600" />
                  <span className="text-sm text-white">
                    This will delete ALL classrooms and related timetable entries. This action cannot be undone!
                  </span>
                </div>
              </div>
              
              <p className="text-secondary mb-6">
                Are you sure you want to proceed? This will permanently delete {classrooms.length} classroom(s) and all related data.
              </p>
              
              <div className="flex gap-3">
                <button
                  onClick={() => setShowDeleteAllConfirm(false)}
                  className="flex-1 py-2 px-4 border border-border rounded-lg text-secondary hover:bg-background transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleDeleteAllClassrooms}
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
                <h3 className="text-lg font-semibold text-primary">Confirm Delete Classroom</h3>
              </div>
              <p className="text-secondary mb-6">
                Are you sure you want to delete this classroom?
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

export default Classrooms;