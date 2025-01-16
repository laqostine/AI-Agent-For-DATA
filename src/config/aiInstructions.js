const teacherDifficultyMap = {
    // Easy difficulty teachers
    "rehber matematik": "Kolay",
    "rehbermatematik": "Kolay",
    "matbook": "Kolay",
    "tonguc": "Kolay",
    "tonguç": "Kolay",

    // Medium difficulty teachers
    "hocalara geldik": "Orta",
    "hocalarageldik": "Orta",
    "matematik kafası": "Orta",
    "matematikkafasi": "Orta",

    // Hard difficulty teachers
    "tunc kurt": "Zor",
    "tunç kurt": "Zor",
    "tunckurt": "Zor",
    "matematik öğreniyorum": "Zor",
    "matematikogreniyorum": "Zor"
};

const analysisPrompt = `You are an expert in analyzing educational content. I will provide you with video content, and you should analyze it to determine the grade level and difficulty.

Consider these factors when analyzing:
1. Channel/Teacher name - Use the predefined difficulty levels for known teachers
2. Content complexity in the title and description
3. Keywords indicating grade level (e.g., "10.sınıf", "11. sınıf")
4. Topic complexity and prerequisites mentioned
5. Teaching approach (basic vs comprehensive)
6. Target audience hints

You must respond with ONLY a JSON object in this exact format:
{
    "grade": "10",
    "difficulty": "Kolay", 
    "confidence": 0.8
}

The grade must be one of: "9", "10", "11", "12"
The difficulty must be one of: "Kolay", "Orta", "Zor"
The confidence must be a number between 0 and 1

Teacher Difficulty Guidelines:
- If the content is from "Rehber Matematik" or "Tonguç", prefer "Kolay" difficulty
- If the content is from "Tunç Kurt", prefer "Zor" difficulty
- For unknown teachers, base difficulty on content analysis
`;

module.exports = {
    teacherDifficultyMap,
    analysisPrompt
}; 