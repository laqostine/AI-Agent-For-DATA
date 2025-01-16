# AI Agent for Educational Content Analysis

This project is an AI-powered tool that analyzes educational video content to determine grade levels and difficulty ratings. It uses the Google Gemini API for content analysis and includes teacher-specific difficulty mappings.

## Features

- Automatic grade level detection (9-12)
- Teacher-specific difficulty ratings
- Content complexity analysis
- YouTube video metadata processing
- Configurable teacher difficulty mappings

## Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/AI-Agent-For-DATA.git
cd AI-Agent-For-DATA
```

2. Install dependencies:
```bash
npm install
```

3. Create a `.env` file in the root directory and add your Gemini API key:
```
GEMINI_API_KEY=your_api_key_here
```

## Usage

Run the application with a search query:
```bash
node src/index.js "Matematik 10.sınıf fonksiyonlar"
```

The application will:
1. Search for relevant educational videos
2. Analyze video content using Gemini AI
3. Determine grade level and difficulty
4. Update the video resources database

## Configuration

Teacher difficulty levels can be configured in `src/config/aiInstructions.js`:
- Easy (Kolay): Rehber Matematik, Tonguç
- Medium (Orta): Hocalara Geldik, Matematik Kafası
- Hard (Zor): Tunç Kurt, Matematik Öğreniyorum

## Project Structure

```
src/
├── config/
│   └── aiInstructions.js   # AI analysis configuration
├── services/
│   ├── geminiService.js    # Gemini AI integration
│   └── dataProcessor.js    # Data processing logic
└── index.js               # Main application entry
```

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 