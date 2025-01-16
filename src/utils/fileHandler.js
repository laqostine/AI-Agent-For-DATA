const fs = require('fs').promises;
const path = require('path');

async function readVideoResources(filePath) {
    try {
        // If file doesn't exist, return empty structure
        try {
            await fs.access(filePath);
        } catch {
            return { YKS: {} };
        }

        const data = await fs.readFile(filePath, 'utf8');
        
        // Extract the JSON object from the file content
        const match = data.match(/export const videoResources = ({[\s\S]*});/);
        if (!match) {
            console.log('Could not parse existing file, starting fresh');
            return { YKS: {} };
        }

        const jsonStr = match[1];
        return JSON.parse(jsonStr);
    } catch (error) {
        console.error('Error reading file:', error);
        return { YKS: {} };
    }
}

async function updateVideoResources(filePath, newVideos, queryInfo) {
    try {
        const resources = await readVideoResources(filePath);
        
        // Ensure the structure exists
        if (!resources.YKS) resources.YKS = {};
        if (!resources.YKS[queryInfo.subject]) resources.YKS[queryInfo.subject] = {};
        
        // Create a proper topic name
        const topicName = queryInfo.topic.charAt(0).toUpperCase() + queryInfo.topic.slice(1);
        
        // Initialize or update the topic array
        if (!resources.YKS[queryInfo.subject][topicName]) {
            resources.YKS[queryInfo.subject][topicName] = [];
        }

        // Add new videos
        resources.YKS[queryInfo.subject][topicName] = newVideos;

        // Convert back to the original format with proper formatting
        const fileContent = `export const videoResources = ${JSON.stringify(resources, null, 2)};\n`;
        await fs.writeFile(filePath, fileContent, 'utf8');
        
        console.log(`Updated ${queryInfo.subject} - ${topicName} with ${newVideos.length} videos`);
        return resources;
    } catch (error) {
        console.error('Error updating video resources:', error);
        throw error;
    }
}

module.exports = { readVideoResources, updateVideoResources }; 