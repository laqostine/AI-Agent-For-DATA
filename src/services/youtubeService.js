const youtube = require('../config/youtube');

async function searchVideos(query, maxResults = 5) {
    try {
        const response = await youtube.search.list({
            part: 'snippet',
            q: query,
            type: 'video',
            maxResults: maxResults,
            relevanceLanguage: 'tr'
        });

        if (!response.data.items || response.data.items.length === 0) {
            console.log('No videos found for query:', query);
            return [];
        }

        const videoIds = response.data.items.map(item => item.id.videoId);
        
        // Get additional video details including duration
        const videoDetails = await youtube.videos.list({
            part: 'contentDetails,snippet',
            id: videoIds.join(',')
        });

        if (!videoDetails.data.items) {
            console.log('Could not fetch video details');
            return [];
        }

        return videoDetails.data.items.map(video => ({
            videoId: video.id,
            title: video.snippet.title,
            description: video.snippet.description || '',
            duration: parseDuration(video.contentDetails.duration),
            url: `https://www.youtube.com/watch?v=${video.id}`
        }));
    } catch (error) {
        console.error('Error searching videos:', error.message);
        if (error.response) {
            console.error('API Response:', error.response.data);
        }
        throw error;
    }
}

function parseDuration(duration) {
    try {
        // Convert ISO 8601 duration to minutes
        const match = duration.match(/PT(\d+H)?(\d+M)?(\d+S)?/);
        
        const hours = (match[1] || '').replace('H', '');
        const minutes = (match[2] || '').replace('M', '');
        const seconds = (match[3] || '').replace('S', '');

        let totalMinutes = 0;
        if (hours) totalMinutes += parseInt(hours) * 60;
        if (minutes) totalMinutes += parseInt(minutes);
        if (seconds) totalMinutes += Math.ceil(parseInt(seconds) / 60);

        return totalMinutes;
    } catch (error) {
        console.error('Error parsing duration:', duration);
        return 0;
    }
}

module.exports = { searchVideos }; 