const { GoogleGenerativeAI } = require('@google/generative-ai');
const { teacherDifficultyMap, analysisPrompt } = require('../config/aiInstructions');
require('dotenv').config();

const genai = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);

const model = genai.getGenerativeModel({
    model: "gemini-1.5-flash",
    generationConfig: {
        temperature: 0,
        topP: 0.95,
        topK: 40,
        maxOutputTokens: 8192,
    }
});

function getTeacherFromContent(title, description) {
    const content = (title + ' ' + description).toLowerCase();
    
    for (const [teacher, difficulty] of Object.entries(teacherDifficultyMap)) {
        if (content.includes(teacher.toLowerCase())) {
            return { teacher, preferredDifficulty: difficulty };
        }
    }
    
    return { teacher: null, preferredDifficulty: null };
}

async function analyzeVideoContent(title, description) {
    try {
        console.log('Starting Gemini analysis for:', title);
        
        // Detect teacher and their preferred difficulty
        const { teacher, preferredDifficulty } = getTeacherFromContent(title, description);
        console.log('Detected teacher:', teacher, 'with preferred difficulty:', preferredDifficulty);

        const chatSession = model.startChat({
            history: [
                {
                    role: "user",
                    parts: [{ text: analysisPrompt }]
                },
                {
                    role: "model",
                    parts: [{
                        text: "I understand. I will analyze the video content and provide a JSON response with the grade level, difficulty, and confidence score in the exact format specified. Please provide the video content to analyze."
                    }]
                }
            ]
        });

        console.log('Sending content to Gemini:', { title, description });
        const result = await chatSession.sendMessage([
            {
                text: `Title: ${title}\nDescription: ${description}${teacher ? `\nTeacher: ${teacher} (Preferred Difficulty: ${preferredDifficulty})` : ''}`
            }
        ]);

        console.log('Received response from Gemini');
        const text = result.response.text();
        console.log('Raw response:', text);
        
        try {
            // Remove any markdown formatting if present
            const cleanJson = text.replace(/```json\n?|\n?```/g, '').trim();
            console.log('Cleaned JSON:', cleanJson);
            const jsonResponse = JSON.parse(cleanJson);
            console.log('Parsed response:', jsonResponse);

            // If we have a preferred difficulty for the teacher, use it
            if (preferredDifficulty) {
                jsonResponse.difficulty = preferredDifficulty;
                // Increase confidence if we're using teacher-specific difficulty
                jsonResponse.confidence = Math.min(1, jsonResponse.confidence + 0.1);
            }

            return {
                grade: jsonResponse.grade,
                difficulty: jsonResponse.difficulty,
                confidence: jsonResponse.confidence
            };
        } catch (parseError) {
            console.error('Error parsing Gemini response:', text);
            throw parseError;
        }
    } catch (error) {
        console.error('Error analyzing content with Gemini:', error);
        // Return default values if analysis fails
        return {
            grade: null,
            difficulty: "Orta",
            confidence: 0.5
        };
    }
}

module.exports = { analyzeVideoContent }; 