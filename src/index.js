const { parseQuery } = require('./utils/queryParser');
const { searchVideos } = require('./services/youtubeService');
const { processVideoData } = require('./services/dataProcessor');
const { updateVideoResources } = require('./utils/fileHandler');
const path = require('path');

async function main(searchQuery) {
    try {
        // Parse the search query
        const queryInfo = parseQuery(searchQuery);
        if (!queryInfo.subject || !queryInfo.grade || !queryInfo.topic) {
            throw new Error('Could not parse query. Please provide subject, grade, and topic.');
        }

        console.log('Searching for videos...');
        const videos = await searchVideos(searchQuery);
        
        console.log('Analyzing video content with Gemini...');
        const processedVideos = await processVideoData(videos, queryInfo);
        
        console.log('Updating video resources...');
        const resourcesPath = path.join(__dirname, '..', 'file.js');
        await updateVideoResources(resourcesPath, processedVideos, queryInfo);
        
        console.log('Successfully updated video resources!');
        return processedVideos;
    } catch (error) {
        console.error('Error in main process:', error);
        throw error;
    }
}

// If running directly (not imported as a module)
if (require.main === module) {
    const searchQuery = process.argv[2];
    if (!searchQuery) {
        console.error('Please provide a search query as an argument');
        process.exit(1);
    }
    
    main(searchQuery)
        .then(() => process.exit(0))
        .catch(error => {
            console.error(error);
            process.exit(1);
        });
}

module.exports = { main }; 