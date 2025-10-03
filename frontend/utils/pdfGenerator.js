import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';
import api from '../pages/utils/api';

export const generateTimetablePDF = async (timetableData, selectedClassGroup = null) => {
  try {
    console.log('Starting PDF generation...');
    console.log('Initial timetable data:', timetableData);
    
    // Always fetch fresh data for all sections when generating PDF
    let allSectionsData = null;
    
    try {
      console.log('Fetching complete timetable data for all sections...');
      // Request all sections by setting a very large page size to bypass pagination
      const response = await api.get('/api/timetable/latest/', {
        params: {
          page_size: 1000, // Large enough to get all sections
          page: 1
        }
      });
      
             if (response.data && response.data.entries && Array.isArray(response.data.entries)) {
         allSectionsData = response.data;
         console.log('✅ Successfully fetched complete data for PDF');
         console.log('Total entries found:', response.data.entries.length);
         console.log('Available class groups from API:', response.data.pagination?.class_groups);
         console.log('📚 Batch info from API:', {
           semester: response.data.semester,
           academic_year: response.data.academic_year,
           batch_info: response.data.batch_info
         });
        
        // Check if we got all sections or if pagination is still limiting us
        const totalClassGroups = response.data.pagination?.total_class_groups || 0;
        const currentClassGroups = response.data.pagination?.class_groups || [];
        const allClassGroupsFromAPI = response.data.pagination?.all_class_groups || [];
        
        console.log(`📊 Pagination info: total=${totalClassGroups}, current=${currentClassGroups.length}, all=${allClassGroupsFromAPI.length}`);
        
        // If we have all_class_groups, use that directly
        if (allClassGroupsFromAPI.length > 0 && allClassGroupsFromAPI.length >= totalClassGroups) {
          console.log(`✅ API returned all ${allClassGroupsFromAPI.length} sections in single request`);
          // Update the class_groups to include all sections
          response.data.pagination.class_groups = allClassGroupsFromAPI;
        }
        // Otherwise, check if pagination is still limiting us
        else if (totalClassGroups > currentClassGroups.length) {
          console.warn(`⚠️  Pagination still limiting results: got ${currentClassGroups.length} out of ${totalClassGroups} total sections`);
          console.log('Attempting to fetch all sections by making multiple requests...');
          
          // Try to fetch all sections by making multiple requests
          let allEntries = [...response.data.entries];
          let allClassGroups = [...currentClassGroups];
          let currentPage = 2;
          
          while (allClassGroups.length < totalClassGroups && currentPage <= 10) { // Safety limit
            try {
              const nextResponse = await api.get('/api/timetable/latest/', {
                params: {
                  page_size: 1000,
                  page: currentPage
                }
              });
              
              if (nextResponse.data?.entries && Array.isArray(nextResponse.data.entries)) {
                allEntries = [...allEntries, ...nextResponse.data.entries];
                const nextClassGroups = nextResponse.data.pagination?.class_groups || [];
                allClassGroups = [...new Set([...allClassGroups, ...nextClassGroups])];
                console.log(`📄 Fetched page ${currentPage}: ${nextResponse.data.entries.length} entries, total sections: ${allClassGroups.length}`);
              }
              
              currentPage++;
            } catch (pageError) {
              console.warn(`⚠️  Error fetching page ${currentPage}:`, pageError);
              break;
            }
          }
          
          // Update the data with all fetched entries
          allSectionsData.entries = allEntries;
          allSectionsData.pagination.class_groups = allClassGroups;
          console.log(`✅ Final data: ${allEntries.length} entries across ${allClassGroups.length} sections`);
        }
        
        // Verify we have all the necessary data
        if (!allSectionsData.days || !allSectionsData.timeSlots) {
          console.warn('⚠️  Missing days or timeSlots from API, using current data');
          allSectionsData.days = timetableData.days || allSectionsData.days;
          allSectionsData.timeSlots = timetableData.timeSlots || allSectionsData.timeSlots;
        }
      } else {
        console.warn('⚠️  API response missing entries, using current data');
        allSectionsData = timetableData;
      }
    } catch (error) {
      console.error('❌ Error fetching complete data:', error);
      console.warn('Using current timetable data instead');
      allSectionsData = timetableData;
    }
    
    // Ensure we have the basic structure
    if (!allSectionsData || !allSectionsData.entries) {
      throw new Error('No timetable data available for PDF generation');
    }
    
    // Final data consistency check
    console.log('\n🔍 Data Consistency Check:');
    console.log('- Total entries in data:', allSectionsData.entries.length);
    console.log('- Unique class groups in entries:', [...new Set(allSectionsData.entries.map(entry => entry.class_group))].length);
    console.log('- Class groups from pagination:', allSectionsData.pagination?.class_groups?.length || 0);
    console.log('- Total class groups reported:', allSectionsData.pagination?.total_class_groups || 0);
    
    // If there's a mismatch, log it for debugging
    const entriesClassGroups = [...new Set(allSectionsData.entries.map(entry => entry.class_group))];
    const paginationClassGroups = allSectionsData.pagination?.class_groups || [];
    const totalReported = allSectionsData.pagination?.total_class_groups || 0;
    
    if (entriesClassGroups.length !== paginationClassGroups.length) {
      console.warn(`⚠️  Mismatch: ${entriesClassGroups.length} class groups in entries vs ${paginationClassGroups.length} in pagination`);
    }
    
    if (totalReported > 0 && totalReported !== paginationClassGroups.length) {
      console.warn(`⚠️  Mismatch: ${paginationClassGroups.length} class groups in pagination vs ${totalReported} total reported`);
    }
    
    // Get ALL unique class groups from the entries data
    const allClassGroupsFromEntries = [...new Set(allSectionsData.entries.map(entry => entry.class_group))];
    console.log('Class groups found in entries:', allClassGroupsFromEntries);
    
    // Get class groups from pagination if available
    // Use all_class_groups for complete list, fallback to class_groups
    const classGroupsFromPagination = allSectionsData.pagination?.all_class_groups || 
                                    allSectionsData.pagination?.class_groups || [];
    console.log('Class groups from pagination:', classGroupsFromPagination);
    
    // Use the union of both sources to ensure we don't miss any sections
    const allClassGroups = [...new Set([...allClassGroupsFromEntries, ...classGroupsFromPagination])];
    
    // Sort class groups logically (batch first, then section)
    allClassGroups.sort((a, b) => {
      const [batchA, sectionA] = a.split('-');
      const [batchB, sectionB] = b.split('-');
      if (batchA !== batchB) return batchA.localeCompare(batchB);
      return (sectionA || '').localeCompare(sectionB || '');
    });
    
    console.log('Final sorted class groups to process:', allClassGroups);
    console.log('Total sections to include:', allClassGroups.length);
    
    // Group class groups by batch
    const batchGroups = {};
    allClassGroups.forEach(classGroup => {
      const [batchName, sectionName] = classGroup.split('-');
      if (!batchGroups[batchName]) {
        batchGroups[batchName] = [];
      }
      batchGroups[batchName].push({
        classGroup,
        sectionName: sectionName || '',
        entries: allSectionsData.entries.filter(entry => entry.class_group === classGroup)
      });
    });
    
    // Sort sections within each batch
    Object.keys(batchGroups).forEach(batchName => {
      batchGroups[batchName].sort((a, b) => a.sectionName.localeCompare(b.sectionName));
    });
    
    console.log('Batch groups created:', Object.keys(batchGroups).map(batch => ({
      batch,
      sections: batchGroups[batch].map(s => s.classGroup)
    })));
    
    // Create PDF document
    const doc = new jsPDF('p', 'mm', 'a4');
    doc.setFont('helvetica');
    
    // Page dimensions
    const pageWidth = doc.internal.pageSize.width;
    const pageHeight = doc.internal.pageSize.height;
    const margin = 20;
    const contentWidth = pageWidth - (2 * margin);
    
    // Header
    doc.setFontSize(16);
    doc.setFont('helvetica', 'bold');
    
    // Split long university name into multiple lines if needed
    const universityName = 'MEHRAN UNIVERSITY OF ENGINEERING AND TECHNOLOGY, JAMSHORO';
    const deptName = 'DEPARTMENT OF SOFTWARE ENGINEERING';
    
    // Check if text fits within content width, if not, reduce font size
    let fontSize = 16;
    let textWidth = doc.getTextWidth(universityName);
    
    while (textWidth > contentWidth && fontSize > 10) {
      fontSize--;
      doc.setFontSize(fontSize);
      textWidth = doc.getTextWidth(universityName);
    }
    
    doc.text(universityName, pageWidth / 2, 30, { align: 'center' });
    
    // Reset font size for department name
    doc.setFontSize(14);
    doc.text(deptName, pageWidth / 2, 40, { align: 'center' });
    
    let currentY = 60;
    let processedBatches = 0;
    
    // Process each batch
    const batchNames = Object.keys(batchGroups).sort();
    for (let batchIndex = 0; batchIndex < batchNames.length; batchIndex++) {
      const batchName = batchNames[batchIndex];
      const batchSections = batchGroups[batchName];
      
      console.log(`📝 Processing batch ${batchName} with ${batchSections.length} sections`);
      
      // Start each batch on a new page (except the first one)
      if (batchIndex > 0) {
        doc.addPage();
        currentY = 30;
        console.log(`📄 Added new page for batch ${batchName}`);
      }
      
             // Get batch description from database
       let batchDescription = '';
       if (allSectionsData.batch_info && allSectionsData.batch_info[batchName]) {
         const batchData = allSectionsData.batch_info[batchName];
         if (batchData.description) {
           batchDescription = batchData.description;
         } else if (batchData.semester_number && batchData.academic_year) {
           batchDescription = `${batchData.semester_number}th Semester ${batchData.academic_year}`;
         } else if (batchData.academic_year) {
           batchDescription = batchData.academic_year;
         }
       }
       
       // Fallback to general semester/academic year if no batch-specific info
       if (!batchDescription) {
         if (allSectionsData.semester && allSectionsData.academic_year) {
           batchDescription = `${allSectionsData.semester} ${allSectionsData.academic_year}`;
         } else if (allSectionsData.semester) {
           batchDescription = allSectionsData.semester;
         } else if (allSectionsData.academic_year) {
           batchDescription = allSectionsData.academic_year;
         } else {
           batchDescription = 'Academic Year';
         }
       }
      
             // Process each section's timetable for this batch
       for (let sectionIndex = 0; sectionIndex < batchSections.length; sectionIndex++) {
         const section = batchSections[sectionIndex];
         const classGroupEntries = section.entries;
         
         if (classGroupEntries.length === 0) {
           console.log(`⚠️  No entries found for ${section.classGroup}, skipping...`);
           continue;
         }
         
         // Section header - full heading for each section
         doc.setFontSize(14);
         doc.setFont('helvetica', 'bold');
         const sectionText = section.sectionName ? `SECTION-${section.sectionName}` : 'MAIN BATCH';
         doc.text(`TIMETABLE OF ${batchName}-BATCH ${sectionText} (${batchDescription})`, pageWidth / 2, currentY, { align: 'center' });
         currentY += 10;
         
         // Add w.e.f. text only for the first section of each batch
         if (sectionIndex === 0) {
           doc.setFontSize(12);
           doc.setFont('helvetica', 'normal');
           const today = new Date();
           const dateString = today.toLocaleDateString('en-GB').split('/').join('-');
           doc.text(`w.e.f ${dateString}`, pageWidth / 2, currentY, { align: 'center' });
           currentY += 15;
         }
        
        // Create timetable table for this section
        const tableData = [];
        
        // Add header row with days
        const headerRow = ['Timing'];
        allSectionsData.days.forEach(day => {
          headerRow.push(day);
        });
        tableData.push(headerRow);
        
        // Add time slots and subjects
        allSectionsData.timeSlots.forEach((timeSlot, index) => {
          let formattedTimeSlot = timeSlot;
          if (timeSlot.includes(' to ')) {
            formattedTimeSlot = timeSlot.replace(' to ', ' - ');
          }
          formattedTimeSlot = formattedTimeSlot.replace(/\s+/g, ' ').trim();
          
          const row = [formattedTimeSlot];
          
          allSectionsData.days.forEach(day => {
            // Find entry by day and period
            let entry = classGroupEntries.find(e => 
              e.day === day && e.period === (index + 1)
            );
            
            // If not found, try normalized day names
            if (!entry) {
              const normalizeDay = (dayName) => {
                if (typeof dayName === 'string') {
                  return dayName.toUpperCase().substring(0, 3);
                }
                return dayName;
              };
              
              entry = classGroupEntries.find(e => 
                normalizeDay(e.day) === normalizeDay(day) && e.period === (index + 1)
              );
            }
            
            if (entry) {
              let subjectShortName = entry.subject_short_name || '';
              let cellContent = subjectShortName || '';
              
              // Add asterisk for extra classes
              if (entry.is_extra_class) {
                cellContent += '*';
              }
              
              // Add room information if different from default
              if (entry.classroom && !entry.classroom.includes('Lab. No.')) {
                cellContent += ` [${entry.classroom}]`;
              }
              
              row.push(cellContent);
            } else {
              row.push('');
            }
          });
          
          tableData.push(row);
        });
        
        // Calculate column widths
        const numDays = allSectionsData.days.length;
        const periodColumnWidth = 35;
        const remainingWidth = contentWidth - periodColumnWidth;
        const dayColumnWidth = Math.max(remainingWidth / numDays, 30);
        
        // Generate the table for this section
        console.log(`  📊 Creating table for ${section.classGroup} with ${tableData.length} rows`);
        autoTable(doc, {
          head: [tableData[0]],
          body: tableData.slice(1),
          startY: currentY,
          margin: { left: margin, right: margin },
          tableWidth: contentWidth,
          styles: {
            fontSize: 10,
            cellPadding: 3,
            lineWidth: 0.1,
            lineColor: [100, 100, 100],
            textColor: [50, 50, 50],
            fillColor: [255, 255, 255],
            overflow: 'linebreak',
            halign: 'center',
          },
          headStyles: {
            fillColor: [70, 70, 70],
            textColor: [255, 255, 255],
            fontSize: 11,
            fontStyle: 'bold',
            halign: 'center',
          },
          columnStyles: {
            0: { cellWidth: periodColumnWidth, halign: 'center', cellPadding: 2, fontSize: 9 },
            ...Array.from({ length: numDays }, (_, i) => i + 1).reduce((acc, colIndex) => {
              acc[colIndex] = { cellWidth: dayColumnWidth, halign: 'center' };
              return acc;
            }, {})
          },
          didDrawPage: function (data) {
            doc.setFontSize(10);
            doc.text(`Page ${doc.internal.getNumberOfPages()}`, pageWidth - margin, pageHeight - 10);
          }
        });
        
        console.log(`  ✅ Table created for ${section.classGroup}. Final Y: ${doc.lastAutoTable.finalY}`);
        currentY = doc.lastAutoTable.finalY + 10;
        
        // Add some space between sections
        if (sectionIndex < batchSections.length - 1) {
          currentY += 5;
        }
      }
      
      // Add consolidated subject and teacher details for the entire batch
      if (currentY > pageHeight - 100) {
        doc.addPage();
        currentY = 30;
      }
      
      doc.setFontSize(12);
      doc.setFont('helvetica', 'bold');
      doc.text('Subject and Teacher Details', margin, currentY);
      currentY += 10;
      
      // Create consolidated teachers table for the entire batch
      const teacherData = [];
      const subjectGroups = {};
      
      console.log(`  🔍 Processing ${batchSections.length} sections for consolidated subject grouping...`);
      
      // Collect all entries from all sections in this batch
      const allBatchEntries = batchSections.flatMap(section => section.entries);
      
      // Group entries by subject name across all sections (excluding extra classes)
      allBatchEntries.forEach(entry => {
        // Skip extra classes in the Subject and Teacher Details table
        if (entry.is_extra_class) {
          return;
        }
        
        const subjectCode = entry.subject_short_name || entry.subject || '';
        const subjectName = entry.subject || '';
        
        // Clean the subject name for display (remove PR suffix if present)
        const cleanSubjectName = subjectName.replace(' (PR)', '').replace('(PR)', '').trim();
        
        if (!subjectGroups[cleanSubjectName]) {
          subjectGroups[cleanSubjectName] = {
            theory: [],
            practical: [],
            subjectName: cleanSubjectName,
            subjectCode: subjectCode,
            allSubjectCodes: new Set([subjectCode])
          };
        } else {
          subjectGroups[cleanSubjectName].allSubjectCodes.add(subjectCode);
        }
        
        // Group by theory/practical and section
        if (entry.is_practical) {
          subjectGroups[cleanSubjectName].practical.push({
            ...entry,
            sectionName: entry.class_group.split('-')[1] || 'MAIN'
          });
        } else {
          subjectGroups[cleanSubjectName].theory.push({
            ...entry,
            sectionName: entry.class_group.split('-')[1] || 'MAIN'
          });
        }
      });
      
      // Convert grouped data to table format with smart teacher grouping
      Object.values(subjectGroups).forEach((group, index) => {
        const theoryEntries = group.theory;
        const practicalEntries = group.practical;
        
        // Determine credit hours
        let creditHours = '';
        if (theoryEntries.length > 0 && practicalEntries.length > 0) {
          const theoryCredits = theoryEntries[0].credits || 3;
          creditHours = `${theoryCredits}+1`;
        } else if (theoryEntries.length > 0) {
          const theoryCredits = theoryEntries[0].credits || 3;
          creditHours = `${theoryCredits}+0`;
        } else if (practicalEntries.length > 0) {
          creditHours = `0+1`;
        }
        
                 // Smart teacher grouping logic
         let teacherNames = '';
         
         if (theoryEntries.length > 0 && practicalEntries.length > 0) {
           // Both theory and practical exist
           const theoryTeachers = [...new Set(theoryEntries.map(e => e.teacher))].filter(t => t && t !== '--');
           const practicalTeachers = [...new Set(practicalEntries.map(e => e.teacher))].filter(t => t && t !== '--');
           
           // Check if same teacher teaches both theory and practical across ALL sections
           const allTheorySections = new Set(theoryEntries.map(e => e.sectionName));
           const allPracticalSections = new Set(practicalEntries.map(e => e.sectionName));
           const totalSections = new Set([...allTheorySections, ...allPracticalSections]);
           
           if (theoryTeachers.length === 1 && practicalTeachers.length === 1 && theoryTeachers[0] === practicalTeachers[0]) {
             // Same teacher for both theory and practical across all sections
             teacherNames = `${theoryTeachers[0]} (Th & Pr)`;
           } else {
             // Check if different teachers but each teacher teaches their type to ALL sections
             const theoryCoversAllSections = allTheorySections.size === batchSections.length;
             const practicalCoversAllSections = allPracticalSections.size === batchSections.length;
             
             if (theoryCoversAllSections && practicalCoversAllSections) {
               // Each teacher type covers all sections - show as Teacher1 (Th) / Teacher2 (Pr)
               const theoryTeacher = theoryTeachers[0];
               const practicalTeacher = practicalTeachers[0];
               teacherNames = `${theoryTeacher} (Th) / ${practicalTeacher} (Pr)`;
             } else {
               // Mixed assignments - show detailed breakdown
               const theoryTeacherGroups = groupTeachersBySections(theoryEntries);
               const practicalTeacherGroups = groupTeachersBySections(practicalEntries);
               
               const theoryPart = formatTeacherGroups(theoryTeacherGroups, 'Th');
               const practicalPart = formatTeacherGroups(practicalTeacherGroups, 'Pr');
               
               teacherNames = [theoryPart, practicalPart].filter(Boolean).join(' / ');
             }
           }
         } else if (theoryEntries.length > 0) {
           // Only theory exists
           const theoryTeacherGroups = groupTeachersBySections(theoryEntries);
           teacherNames = formatTeacherGroups(theoryTeacherGroups, 'Th');
         } else if (practicalEntries.length > 0) {
           // Only practical exists
           const practicalTeacherGroups = groupTeachersBySections(practicalEntries);
           teacherNames = formatTeacherGroups(practicalTeacherGroups, 'Pr');
         }
         
         // Check if same teacher teaches this subject to ALL sections (both theory and practical combined)
         // BUT only if we haven't already set teacherNames to (Th & Pr) format
         if (!teacherNames.includes('(Th & Pr)')) {
           const allEntriesForSubject = [...theoryEntries, ...practicalEntries];
           const allTeachersForSubject = [...new Set(allEntriesForSubject.map(e => e.teacher))].filter(t => t && t !== '--');
           const allSectionsForSubject = new Set(allEntriesForSubject.map(e => e.sectionName));
           
           // If only one teacher teaches this subject to all sections, show just the teacher name
           if (allTeachersForSubject.length === 1 && allSectionsForSubject.size === batchSections.length) {
             teacherNames = allTeachersForSubject[0];
           }
         }
        
        // Format subject name as "subject name - subject code"
        let formattedSubjectName = group.subjectName;
        // Get the actual subject code from the entry data
        const firstEntry = [...group.theory, ...group.practical][0];
        if (firstEntry && firstEntry.subject_code && firstEntry.subject_code.trim()) {
          formattedSubjectName = `${group.subjectName} - ${firstEntry.subject_code}`;
        }
        
        teacherData.push([
          index + 1,
          formattedSubjectName,
          creditHours,
          teacherNames
        ]);
      });
      
      // Add consolidated teachers table
      console.log(`  👥 Creating consolidated teachers table for batch ${batchName} with ${teacherData.length} subjects`);
      
      autoTable(doc, {
        head: [['S.', 'SUBJECT NAME', 'C.H', 'TEACHER']],
        body: teacherData,
        startY: currentY,
        margin: { left: margin, right: margin },
        tableWidth: contentWidth,
        styles: {
          fontSize: 9,
          cellPadding: 3,
          lineWidth: 0.1,
          lineColor: [100, 100, 100],
          textColor: [50, 50, 50],
          fillColor: [255, 255, 255],
        },
        headStyles: {
          fillColor: [70, 70, 70],
          textColor: [255, 255, 255],
          fontSize: 10,
          fontStyle: 'bold',
          halign: 'center',
        },
        columnStyles: {
          0: { cellWidth: 15, halign: 'center' },
          1: { cellWidth: 60, halign: 'left' },
          2: { cellWidth: 25, halign: 'center' },
          3: { cellWidth: 80 },
        }
      });
      
      console.log(`  ✅ Consolidated teachers table created for batch ${batchName}. Final Y: ${doc.lastAutoTable.finalY}`);
      currentY = doc.lastAutoTable.finalY + 20;
      
      // Add additional information
      const spaceNeeded = 45;
      if (currentY > pageHeight - spaceNeeded) {
        doc.addPage();
        currentY = 30;
      }
      
      doc.setFontSize(10);
      doc.setFont('helvetica', 'normal');
      
      // Get class advisor from batch info
      let classAdvisorText = 'Class Advisor: Not Assigned';
      if (allSectionsData.batch_info && allSectionsData.batch_info[batchName]) {
        const batchData = allSectionsData.batch_info[batchName];
        if (batchData.class_advisor && batchData.class_advisor.trim()) {
          classAdvisorText = `Class Advisor: ${batchData.class_advisor}`;
        }
      }
      
      doc.text(classAdvisorText, margin, currentY);
      currentY += 15;
      
      // Signature line
      doc.setFontSize(12);
      doc.setFont('helvetica', 'bold');
      doc.text('Chairman', pageWidth - margin - 30, currentY);
      
      currentY += 30;
      
      processedBatches++;
      console.log(`✅ Completed processing batch ${batchName}`);
    }
    
    // Final verification
    console.log(`\n📋 PDF Generation Summary:`);
    console.log(`- Total batches available: ${Object.keys(batchGroups).length}`);
    console.log(`- Batches processed: ${processedBatches}`);
    console.log(`- Total PDF pages: ${doc.internal.getNumberOfPages()}`);
    
    if (processedBatches === 0) {
      console.error(`❌ No batches with data found!`);
      throw new Error('No timetable data available for any batches');
    }
    
    console.log(`✅ All ${processedBatches} batches successfully included in PDF`);
    
    // Save the PDF with dynamic academic year and date
    const today = new Date();
    const dateString = today.toLocaleDateString('en-GB').split('/').join('-');
    
    // Get academic year from batch data
    let academicYear = 'Unknown';
    if (allSectionsData.batch_info && Object.keys(allSectionsData.batch_info).length > 0) {
      const firstBatchKey = Object.keys(allSectionsData.batch_info)[0];
      const firstBatch = allSectionsData.batch_info[firstBatchKey];
      if (firstBatch && firstBatch.academic_year) {
        academicYear = firstBatch.academic_year;
      }
    } else if (allSectionsData.academic_year) {
      academicYear = allSectionsData.academic_year;
    }
    
    const fileName = `timetable_${academicYear}_${dateString}.pdf`;
    console.log(`💾 Saving PDF as: ${fileName}`);
    doc.save(fileName);
    
    console.log(`🎉 PDF generation completed successfully!`);
    
  } catch (error) {
    console.error('❌ Error generating PDF:', error);
    throw error;
  }
};

// Helper function to group teachers by sections
function groupTeachersBySections(entries) {
  const teacherGroups = {};
  
  entries.forEach(entry => {
    const teacher = entry.teacher || '--';
    const sectionName = entry.sectionName || 'MAIN';
    
    if (!teacherGroups[teacher]) {
      teacherGroups[teacher] = new Set();
    }
    teacherGroups[teacher].add(sectionName);
  });
  
  return teacherGroups;
}

// Helper function to format teacher groups with proper section labeling
function formatTeacherGroups(teacherGroups, type) {
  const parts = [];
  
  Object.entries(teacherGroups).forEach(([teacher, sections]) => {
    if (teacher === '--') return;
    
    const sectionList = Array.from(sections).sort();
    
    if (sectionList.length === 1) {
      // Single section - show section name
      const sectionLabel = getSectionLabel(sectionList[0]);
      parts.push(`${teacher} (${sectionLabel})`);
    } else {
      // Multiple sections - show all section names
      const sectionLabels = sectionList.map(section => getSectionLabel(section));
      parts.push(`${teacher} (${sectionLabels.join('+')})`);
    }
  });
  
  return parts.join(' / ');
}

// Helper function to convert section names to proper labels
function getSectionLabel(sectionName) {
  if (sectionName === 'MAIN') return 'I';
  if (sectionName === 'A') return 'I';
  if (sectionName === 'B') return 'II';
  if (sectionName === 'C') return 'III';
  if (sectionName === 'D') return 'IV';
  return sectionName;
}
