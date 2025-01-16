const { analyzeVideoContent } = require('./geminiService');

async function processVideoData(videos, queryInfo) {
    const processedVideos = [];
    
    for (const video of videos) {
        // Use Gemini to analyze the content
        const analysis = await analyzeVideoContent(video.title, video.description);
        
        processedVideos.push({
            id: (processedVideos.length + 1).toString(),
            grade: analysis.grade || queryInfo.grade,
            subject: queryInfo.subject,
            topic: queryInfo.topic,
            title: video.title,
            description: video.description,
            url: video.url,
            duration: video.duration,
            difficulty: analysis.difficulty || inferDifficultyFallback(video.title, video.description)
        });
    }
    
    return processedVideos;
}

// Fallback function in case Gemini analysis fails
function inferDifficultyFallback(title, description) {
    const content = (title + ' ' + description).toLowerCase();
    
    if (content.includes('temel') || content.includes('basic') || content.includes('başlangıç')) {
        return 'Kolay';
    } else if (content.includes('ileri') || content.includes('advanced') || content.includes('zor')) {
        return 'Zor';
    }
    
    return 'Orta';
}

module.exports = { processVideoData }; 