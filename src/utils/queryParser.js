function parseQuery(query) {
    // Convert query to lowercase for easier matching
    const lowerQuery = query.toLowerCase();
    
    // Extract grade (assuming format like "10.sınıf" or "10")
    const gradeMatch = lowerQuery.match(/(\d+)\.?\s*sınıf/);
    const grade = gradeMatch ? gradeMatch[1] : null;
    
    // Extract subject (predefined list of subjects)
    const subjects = ['matematik', 'fizik', 'kimya'];
    const subject = subjects.find(s => lowerQuery.includes(s));
    
    // Extract topic (everything after the grade and subject)
    let topic = null;
    if (grade && subject) {
        const afterGradeAndSubject = lowerQuery.split(subject)[1];
        if (afterGradeAndSubject) {
            topic = afterGradeAndSubject.trim();
        }
    }
    
    return {
        grade,
        subject: subject ? subject.charAt(0).toUpperCase() + subject.slice(1) : null,
        topic: topic ? topic.charAt(0).toUpperCase() + topic.slice(1) : null
    };
}

module.exports = { parseQuery }; 