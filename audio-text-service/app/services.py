import os
import logging
from pathlib import Path
import httpx
from typing import List, Dict, Any
from datetime import datetime
import torch
import torchaudio
import warnings
import numpy as np
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

from .config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

class AudioTextService:
    def __init__(self):
        try:
            if torch.cuda.is_available():
                torch.backends.cuda.matmul.allow_tf32 = True
                torch.backends.cudnn.allow_tf32 = True
                self.device = torch.device("cuda")
                logger.info("CUDA is available. Using GPU.")
            else:
                self.device = torch.device("cpu")
                logger.info("CUDA is not available. Using CPU.")
            
            logger.info("Loading Whisper model...")
            try:
                model_id = "openai/whisper-large-v3-turbo"
                torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
                
                self.whisper_model = AutoModelForSpeechSeq2Seq.from_pretrained(
                    model_id, 
                    torch_dtype=torch_dtype, 
                    low_cpu_mem_usage=True, 
                    use_safetensors=True
                ).to(self.device)
                
                self.processor = AutoProcessor.from_pretrained(model_id)
                
                # Configure processor to handle attention masks properly for Whisper models
                # Whisper models don't have a separate pad token, so we need to handle this carefully
                self.processor.tokenizer.padding_side = "right"
                
                self.whisper_pipeline = pipeline(
                    "automatic-speech-recognition",
                    model=self.whisper_model,
                    tokenizer=self.processor.tokenizer,
                    feature_extractor=self.processor.feature_extractor,
                    torch_dtype=torch_dtype,
                    device=self.device,
                    model_kwargs={
                        "use_cache": True
                    }
                )
                logger.info("Successfully loaded Whisper model")
            except Exception as e:
                logger.error(f"Failed to load Whisper model: {str(e)}")
                raise
            
            logger.info("Successfully initialized AudioTextService")
            
        except Exception as e:
            logger.error(f"Failed to initialize AudioTextService: {str(e)}")
            self.whisper_model = None
            self.whisper_pipeline = None
            raise
        
        # Create directories if they don't exist
        settings.audio_dir.mkdir(exist_ok=True)
        settings.text_dir.mkdir(exist_ok=True)

    async def get_video_details(self, video_id: str) -> Dict[str, Any]:
        """Get video details from database service"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{settings.db_service_url}{settings.api_prefix}/videos/{video_id}")
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error getting video details: {str(e)}")
            raise

    async def update_video_status(self, video_id: str, status: str) -> None:
        """Update video status in database"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    f"{settings.db_service_url}{settings.api_prefix}/videos/{video_id}",
                    json={"text_status": status}
                )
                response.raise_for_status()
        except Exception as e:
            logger.error(f"Error updating video status: {str(e)}")
            raise

    async def create_text_content(self, video_id: str, title: str, text_file_path: str) -> None:
        """Create text content record in database"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.db_service_url}{settings.api_prefix}/text-contents/",
                    json={
                        "video_id": video_id,
                        "title": title,
                        "text_file_path": text_file_path
                    }
                )
                response.raise_for_status()
        except Exception as e:
            logger.error(f"Error creating text content: {str(e)}")
            raise

    async def process_audio(self, video_id: str, start: float = None, end: float = None) -> bool:
        """Process audio file and create text content"""
        try:
            if self.whisper_pipeline is None:
                logger.error("Whisper model not initialized")
                return False

            # Get video info from database
            logger.info(f"Fetching video details for {video_id}")
            try:
                video_info = await self.get_video_details(video_id)
                logger.info(f"Video info retrieved: {video_info}")
            except Exception as e:
                logger.error(f"Error fetching video details: {str(e)}")
                return False

            if not video_info:
                logger.error(f"Failed to get video info for {video_id}")
                return False
            
            audio_path = video_info.get("audio_file_path")
            if not audio_path:
                logger.error(f"No audio file path found for video {video_id}")
                return False

            # Ensure the audio file exists
            logger.info(f"Checking audio file at: {audio_path}")
            if not os.path.exists(audio_path):
                logger.error(f"Audio file not found at {audio_path}")
                return False
            
            # Preprocess audio
            logger.info("Preprocessing audio...")
            try:
                # Load and normalize audio
                waveform, sample_rate = torchaudio.load(audio_path)
                if waveform.shape[0] > 1:
                    waveform = torch.mean(waveform, dim=0, keepdim=True)
                
                # Apply noise reduction and normalization
                waveform = waveform / torch.max(torch.abs(waveform))
                
                # Save preprocessed audio
                preprocessed_path = f"/tmp/preprocessed_{video_id}.wav"
                torchaudio.save(preprocessed_path, waveform, sample_rate)
                
                # Transcribe the entire audio
                logger.info("Starting transcription...")
                result = self.whisper_pipeline(
                    preprocessed_path,
                    chunk_length_s=30,
                    stride_length_s=5,
                    generate_kwargs={
                        "language": "romanian",
                        "task": "transcribe"
                    }
                )
                
                # Clean up preprocessed file
                os.remove(preprocessed_path)
                
                # Save transcription results
                # Use absolute path to ensure we write to the correct directory
                text_path = Path.cwd().parent / "downloaded_text" / f"{video_id}.txt"
                logger.info(f"Saving transcription results to: {text_path}")
                
                # Ensure the directory exists and has proper permissions
                try:
                    text_path.parent.mkdir(parents=True, exist_ok=True)
                    logger.info(f"Ensured directory exists: {text_path.parent}")
                except Exception as e:
                    logger.error(f"Error creating directory {text_path.parent}: {str(e)}")
                    return False
                
                try:
                    with open(text_path, "w", encoding="utf-8") as f:
                        f.write(f"{result['text']}\n")
                    logger.info("Successfully saved transcription results")
                except PermissionError as e:
                    logger.error(f"Permission denied writing to {text_path}: {str(e)}")
                    logger.error(f"Current working directory: {os.getcwd()}")
                    logger.error(f"Directory permissions: {oct(os.stat(text_path.parent).st_mode)[-3:]}")
                    return False
                except Exception as e:
                    logger.error(f"Error writing to {text_path}: {str(e)}")
                    return False
                
            except Exception as e:
                logger.error(f"Error in transcription: {str(e)}")
                logger.error(f"Error type: {type(e)}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                return False
            
            # Save to database
            logger.info("Saving text content to database")
            try:
                # Use relative path for database storage
                relative_text_path = f"../downloaded_text/{video_id}.txt"
                await self.create_text_content(
                    video_id=video_id,
                    title=video_info.get("title", ""),
                    text_file_path=relative_text_path
                )
                logger.info("Successfully saved text content to database")
            except Exception as e:
                logger.error(f"Error saving text content to database: {str(e)}")
                return False
            
            # Update video status to TEXT
            logger.info("Updating video status to TEXT")
            try:
                await self.update_video_status(video_id, "TEXT")
                logger.info("Successfully updated video status")
            except Exception as e:
                logger.error(f"Error updating video status: {str(e)}")
                return False
            
            logger.info(f"Successfully processed video {video_id}")
            return True
                
        except Exception as e:
            logger.error(f"Error processing audio: {str(e)}")
            logger.error(f"Error type: {type(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            try:
                await self.update_video_status(video_id, "NOT_TEXT")
            except:
                pass
            return False

    def save_text_file(self, video_id: str, segments: List[Dict[str, Any]]) -> str:
        """Save segments to text file"""
        text_file_path = settings.text_dir / f"{video_id}.txt"
        
        with open(text_file_path, "w", encoding="utf-8") as f:
            for segment in segments:
                f.write(f"{segment['start']:.2f}s - {segment['end']:.2f}s: {segment['label']}\n")
        
        return str(text_file_path)

    async def process_video(self, video_id: str) -> Dict[str, Any]:
        """Process a video and convert it to text"""
        try:
            # Get video details
            video = await self.get_video_details(video_id)
            if not video:
                return {
                    "status": "error",
                    "message": f"Video with ID {video_id} not found."
                }

            if video["text_status"] == "TEXT":
                return {
                    "status": "info",
                    "message": f"Video {video_id} is already processed."
                }

            # Update status to PROCESSING
            await self.update_video_status(video_id, "PROCESSING")

            # Process audio file
            audio_file_path = f"{settings.audio_dir}/{os.path.basename(video['audio_file_path'])}"
            if not os.path.exists(audio_file_path):
                await self.update_video_status(video_id, "NOT_TEXT")
                return {
                    "status": "error",
                    "message": f"Audio file not found at {audio_file_path}"
                }

            try:
                success = await self.process_audio(video_id)
                if not success:
                    await self.update_video_status(video_id, "NOT_TEXT")
                    return {
                        "status": "error",
                        "message": f"Failed to process audio for video {video_id}"
                    }

                return {
                    "status": "success",
                    "message": f"Video {video_id} processed successfully",
                    "video_id": video_id
                }

            except Exception as e:
                logger.error(f"Error processing audio file: {str(e)}")
                await self.update_video_status(video_id, "NOT_TEXT")
                return {
                    "status": "error",
                    "message": f"Error processing audio file: {str(e)}"
                }

        except Exception as e:
            logger.error(f"Error processing video {video_id}: {str(e)}")
            try:
                await self.update_video_status(video_id, "NOT_TEXT")
            except:
                pass
            return {
                "status": "error",
                "message": str(e)
            } 