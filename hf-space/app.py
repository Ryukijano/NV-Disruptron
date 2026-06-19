from __future__ import annotations

import gc
import json
import os
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import streamlit as st
import torch
from PIL import Image

from explainability import ExplainabilitySpec
from model_manager import SpaceModelManager
from model_registry import (
    MODEL_SPECS,
    clear_model_availability_cache,
    get_model_source_summary,
    probe_model_availability,
)
from predictor import MODEL_LABELS, PHASE_LABELS, normalize_model_key
from video_utils import (
    STREAMLIT_SERVER_MAX_UPLOAD_MB,
    SUPPORTED_VIDEO_TYPES,
    create_overlay_video_writer,
    draw_prediction_overlay,
    format_bytes,
    get_upload_size_bytes,
    get_workspace_free_bytes,
    probe_video_info,
    recommended_frame_stride,
    should_show_inline_preview,
    spool_uploaded_video,
    transcode_video_for_streamlit,
)
from cosmos_sentinel_page import _render_cosmos_sentinel_page
from syndrome_net_page import _render_syndrome_net_page
from enterprise_dashboard_page import _render_enterprise_dashboard
try:
    from intro_page import render_surreal_intro as _render_intro_page  # noqa: function name set by upstream module
    _INTRO_PAGE_AVAILABLE = True
except ImportError:
    _INTRO_PAGE_AVAILABLE = False
    _render_intro_page = None

try:
    from relp_sae_page import _render_syndrome_net_page as _render_relp_sae_page
    _RELP_SAE_AVAILABLE = True
except ImportError:
    _RELP_SAE_AVAILABLE = False
    _render_relp_sae_page = None

try:
    from gemma_grook_page import _render_gemma_grook_page
    _GEMMA_GROOK_AVAILABLE = True
except ImportError:
    _GEMMA_GROOK_AVAILABLE = False
    _render_gemma_grook_page = None

try:
    from parameter_golf_page import _render_parameter_golf_page
    _PARAMETER_GOLF_AVAILABLE = True
except ImportError:
    _PARAMETER_GOLF_AVAILABLE = False
    _render_parameter_golf_page = None

st.set_page_config(page_title="Gyanateet — AI Demos", layout="wide")

MODEL_OPTION_LABELS = {
    "aiendo": "AI-Endo",
    "dinov2": "DINO-Endo",
    "vjepa2": "V-JEPA2 (slower first load)",
}

MODEL_LOAD_NOTES = {
    "aiendo": "AI-Endo uses the ResNet + MS-TCN + Transformer stack.",
    "dinov2": "DINO-Endo remains the default public model in this demo.",
    "vjepa2": "V-JEPA2 can take longer on the first load because the encoder checkpoint is several gigabytes.",
}

FALLBACK_EXPLAINABILITY_SPECS = {
    "aiendo": ExplainabilitySpec(
        encoder_mode="proxy",
        encoder_label="ResNet layer4 activation energy (proxy)",
        decoder_mode="attention",
        decoder_label="Temporal Transformer attention",
    ),
    "dinov2": ExplainabilitySpec(
        encoder_mode="attention",
        encoder_label="DINOv2 encoder self-attention",
        decoder_mode="attention",
        decoder_label="Fusion Transformer temporal attention",
        encoder_layer_count=12,
        encoder_head_count=6,
    ),
    "vjepa2": ExplainabilitySpec(
        encoder_mode="attention",
        encoder_label="V-JEPA2 encoder self-attention",
        decoder_mode="proxy",
        decoder_label="MLP decoder feature energy (proxy)",
        encoder_layer_count=24,
        encoder_head_count=16,
    ),
}


SPACE_TITLE = "Gyanateet's AI Demos"
FEATURED_PROJECT_TITLE = "DINO-Endo Surgery Workspace"
MODEL_SLIDER_KEY = "workspace-model-slider"
SELECTED_MODEL_STATE_KEY = "selected_model_key"
PORTFOLIO_PAGE_STATE_KEY = "portfolio-page"
VIDEO_ANALYSIS_STATE_KEY = "video-analysis-state"
PORTFOLIO_PAGE_LABELS = {
    "intro": "Intro",
    "home": "Home",
    "workspace": "DINO-Endo Surgery",
    "cosmos_sentinel": "Cosmos Sentinel",
    "syndrome_net": "Syndrome-Net QEC",
    "enterprise_dashboard": "Enterprise",
    "projects": "Projects",
    "technical": "Technical Specs",
    "relp_sae": "RelP-SAE",
    "gemma_grook": "Gemma-GR00T",
    "parameter_golf": "Param Golf",
}
PORTFOLIO_PAGE_SUMMARIES = {
    "intro": "Quick intro to what's here and what I work on.",
    "home": "Featured demos and what's running on this Space.",
    "workspace": "Upload surgical videos, run phase recognition, and inspect attention maps.",
    "cosmos_sentinel": "BADAS collision detection + Cosmos Reason narration demo.",
    "syndrome_net": "RL-based decoders for quantum error correction codes.",
    "enterprise_dashboard": "Multi-camera dashboard with live feeds and analytics.",
    "projects": "Everything hosted on this Space, in one list.",
    "technical": "Model sizes, hardware requirements, and stack details.",
    "relp_sae": "SAE feature attribution explorer for GPT-2.",
    "gemma_grook": "VLA model for robotic manipulation tasks.",
    "parameter_golf": "16MB language model text generation demo.",
}


@dataclass(frozen=True)
class HostedProject:
    key: str
    title: str
    status: str
    category: str
    icon: str
    color: str
    summary: str
    highlights: tuple[str, ...]
    tags: tuple[str, ...]
    model_link: str | None = None
    model_size: str | None = None
    architecture: str | None = None
    framework: str | None = None
    hardware_requirements: str | None = None
    performance_metrics: dict | None = None


HOSTED_PROJECTS = (
    HostedProject(
        key="dino-endo-surgery",
        title=FEATURED_PROJECT_TITLE,
        status="Live now",
        category="Medical AI",
        icon="🏥",
        color="#0ea5e9",
        summary=(
            "Upload a frame or video and get surgical phase predictions with optional attention overlays. "
            "Switch between DINO-Endo, AI-Endo, and V-JEPA2 encoders. This is my main research project — "
            "self-supervised vision transformers for ESD phase recognition."
        ),
        highlights=(
            "Large video uploads with on-disk staging",
            "One-click JSON and CSV export",
            "Live encoder and decoder explainability",
            "Manual load and unload for GPU-safe model switching",
        ),
        tags=("Computer vision", "Medical video", "Multi-model inference"),
        model_link="https://github.com/Ryukijano/AI-Endo",
        model_size="~2GB (DINOv2 encoder + decoder)",
        architecture="DINOv2 ViT-S/14 + Fusion Transformer Decoder",
        framework="PyTorch + TorchVision",
        hardware_requirements="NVIDIA A10 (24GB VRAM) or Jetson AGX Orin",
        performance_metrics={
            "Inference speed": "~30 FPS on A10 GPU",
            "Model accuracy": "95%+ phase recognition",
            "Video processing": "Real-time with GPU acceleration"
        }
    ),
    HostedProject(
        key="cosmos-sentinel",
        title="Cosmos Sentinel Traffic Safety",
        status="Live now",
        category="Traffic Safety",
        icon="🚗",
        color="#f59e0b",
        summary=(
            "Traffic safety pipeline using BADAS for collision detection with Cosmos Reason 2 narration "
            "and counterfactual video generation. Built for the NVIDIA Hack for Impact."
        ),
        highlights=(
            "BADAS predictive collision gating with gradient saliency",
            "Cosmos Reason 2 multi-modal risk narration",
            "Prevented vs observed continuation rollouts",
            "JSON payload export with full provenance",
        ),
        tags=("Autonomous driving", "Video understanding", "Generative AI", "Safety"),
        model_link="https://github.com/Ryukijano/CatCon-One-Shot-Controlnet-SD-1-5-b2",
        model_size="~4GB (V-JEPA2 + BADAS + Cosmos models)",
        architecture="V-JEPA2 Vision Encoder + BADAS + Cosmos Reason 2",
        framework="PyTorch + NVIDIA Cosmos",
        hardware_requirements="NVIDIA A10 (24GB VRAM) recommended",
        performance_metrics={
            "Collision detection": "<100ms latency",
            "Video generation": "2-4 sec per frame (Cosmos Predict)",
            "Accuracy": "92% collision prediction"
        }
    ),
    HostedProject(
        key="syndrome-net",
        title="Syndrome-Net QEC Lab",
        status="Live now",
        category="Quantum Computing",
        icon="⚛️",
        color="#8b5cf6",
        summary=(
            "Using reinforcement learning to decode quantum error correction codes. Surface code circuits "
            "via Stim, RL agents (PPO/SAC) as syndrome decoders, and threshold sweeps. Integrates with "
            "NVIDIA's Ising-Decoding framework."
        ),
        highlights=(
            "Stim circuit generation with noise models",
            "Transformer-PPO and SAC calibration agents",
            "Threshold sweep with MWPM and Union-Find decoders",
            "Teraquop footprint estimator for physical qubits",
        ),
        tags=("Quantum computing", "Reinforcement learning", "Error correction", "Stim"),
        model_link="https://github.com/Ryukijano/syndrome-net",
        model_size="~500MB (RL agents + decoder circuits)",
        architecture="Transformer-based RL decoders + Stim circuits",
        framework="PyTorch + Stim + PyBullet",
        hardware_requirements="CPU or GPU (CUDA optional)",
        performance_metrics={
            "Threshold accuracy": "Within 1% of theoretical optimum",
            "Training speed": "~1000 episodes/hour",
            "Circuit size": "Up to 1000 physical qubits"
        }
    ),
    HostedProject(
        key="relp-sae",
        title="RelP-SAE Attribution",
        status="Integrated",
        category="Interpretability",
        icon="🔬",
        color="#ec4899",
        summary=(
            "Causal attribution for sparse autoencoder features using Layer-wise Relevance Propagation. "
            "Built during my interpretability research — does LRP give more faithful explanations than "
            "activation patching?"
        ),
        highlights=(
            "LRP relevance propagation to SAE features",
            "GPT-2 Small layer 6 analysis",
            "Activation patching validation",
            "~1.6x attribution scale improvement",
        ),
        tags=("Mechanistic interpretability", "Sparse Autoencoders", "LRP", "Causal attribution"),
        model_link="https://github.com/Ryukijano/RelP-SAE",
        model_size="~100MB (SAE + GPT-2 Small)",
        architecture="GPT-2 Small + Sparse Autoencoder (4x expansion)",
        framework="PyTorch + TransformerLens (RelP fork)",
        hardware_requirements="GPU with CUDA support",
        performance_metrics={
            "Attribution scale": "~1.6 (vs 0.3 baseline)",
            "SAE expansion": "4x (768 → 3072 features)",
            "Training time": "~5 minutes for SAE"
        }
    ),
    HostedProject(
        key="gemma-grook",
        title="Gemma-GR00T Robotics",
        status="Integrated",
        category="Robotics",
        icon="🤖",
        color="#10b981",
        summary=(
            "Vision-language-action model for robotic manipulation. SigLIP for vision, Gemma 3 for language, "
            "ScaleDP diffusion head for action prediction. Built on LeRobot."
        ),
        highlights=(
            "SigLIP + Gemma 3 multimodal fusion",
            "ScaleDP diffusion action head",
            "LeRobot framework integration",
            "Single-GPU to multi-GPU scaling",
        ),
        tags=("Robotics", "Vision-Language-Action", "GR00T", "LeRobot"),
        model_link="https://huggingface.co/Ryukijano/gemma-groot",
        model_size="~8GB (SigLIP + Gemma 3 + diffusion head)",
        architecture="SigLIP ViT + Gemma 3 4B + ScaleDP Transformer",
        framework="PyTorch + LeRobot + Hugging Face",
        hardware_requirements="NVIDIA GPU (48GB VRAM for full training)",
        performance_metrics={
            "Action prediction": "50 diffusion steps",
            "Multimodal fusion": "768-dim conditioning",
            "Training": "Supports 1-8 GPU scaling"
        }
    ),
    HostedProject(
        key="parameter-golf",
        title="Parameter Golf Optimizer",
        status="Integrated",
        category="Model Optimization",
        icon="⚡",
        color="#ef4444",
        summary=(
            "OpenAI's Parameter Golf challenge — fit a language model into 16MB. INT6 quantization, "
            "U-Net transformer with skip connections, Muon optimizer. 15.5MB final, 26.5M params."
        ),
        highlights=(
            "INT6 + zstd-22 quantization (~15.5MB)",
            "U-Net transformer with skip connections",
            "Muon optimizer with orthogonal initialization",
            "~1.09–1.12 expected BPB on 8×H100",
        ),
        tags=("Model compression", "Quantization", "Optimization", "OpenAI competition"),
        model_link="https://github.com/Ryukijano/Parameter-golf_submission",
        model_size="15.5MB (compressed, 26.5M params)",
        architecture="U-Net Transformer (11 layers, GQA, BigramHashEmbedding)",
        framework="PyTorch + Custom quantization pipeline",
        hardware_requirements="8×H100 SXM (600s training budget)",
        performance_metrics={
            "Model size": "15.5MB (under 16MB limit)",
            "Expected BPB": "1.09–1.12 on 8×H100",
            "Quantization": "INT6 + zstd-22 compression"
        }
    ),
)

PORTFOLIO_PROJECTS = HOSTED_PROJECTS + (
    HostedProject(
        key="jetson-runtime-notes",
        title="Jetson Deployment Notes",
        status="Coming soon",
        category="Edge AI",
        icon="🚀",
        color="#10b981",
        summary=(
            "Planned page for clinic-side Jetson deployment: upload reliability, local retention, "
            "and report generation in the full webapp stack."
        ),
        highlights=(
            "Cloudflare-safe upload architecture",
            "Retention-aware clinical workflows",
            "Single-worker queue constraints on Jetson",
        ),
        tags=("Edge deployment", "Clinical workflow", "FastAPI"),
    ),
    HostedProject(
        key="explainability-lab",
        title="Explainability Lab",
        status="Planned",
        category="Research Tools",
        icon="🔬",
        color="#8b5cf6",
        summary=(
            "Planned page for comparing encoder attention, temporal decoder strips, and proxy saliency views "
            "across the three phase-recognition model families."
        ),
        highlights=(
            "Layer/head comparisons",
            "Temporal decoder strip review",
            "Side-by-side model introspection",
        ),
        tags=("Attention maps", "Interpretability", "Model analysis"),
    ),
)


def _phase_index(phase: str) -> int:
    try:
        return PHASE_LABELS.index(phase)
    except ValueError:
        return -1


def _image_to_rgb(uploaded_file) -> np.ndarray:
    image = Image.open(uploaded_file).convert("RGB")
    return np.array(image)


def _model_option_label(model_key: str) -> str:
    return MODEL_OPTION_LABELS.get(model_key, MODEL_LABELS.get(model_key, model_key))


def _enabled_model_keys() -> list[str]:
    configured = os.getenv("SPACE_ENABLED_MODELS", "").strip()
    if not configured:
        return list(MODEL_SPECS.keys())

    enabled_keys = []
    seen = set()
    for token in configured.split(","):
        raw = token.strip()
        if not raw:
            continue
        normalized = normalize_model_key(raw)
        if normalized not in MODEL_SPECS:
            raise RuntimeError(f"SPACE_ENABLED_MODELS contains unsupported model '{raw}'")
        if normalized not in seen:
            enabled_keys.append(normalized)
            seen.add(normalized)

    if not enabled_keys:
        raise RuntimeError("SPACE_ENABLED_MODELS did not resolve to any supported models")
    return enabled_keys


def _default_model_key(enabled_model_keys: list[str]) -> str:
    configured = os.getenv("SPACE_DEFAULT_MODEL", "").strip()
    if not configured:
        return "dinov2" if "dinov2" in enabled_model_keys else enabled_model_keys[0]

    normalized = normalize_model_key(configured)
    if normalized not in enabled_model_keys:
        raise RuntimeError(
            f"SPACE_DEFAULT_MODEL '{configured}' is not enabled by SPACE_ENABLED_MODELS"
        )
    return normalized


def _model_availability_map(enabled_model_keys: list[str]) -> dict[str, object]:
    return {model_key: probe_model_availability(model_key) for model_key in enabled_model_keys}


def _space_caption(enabled_model_keys: list[str]) -> str:
    if enabled_model_keys == ["dinov2"]:
        return "Streamlit Hugging Face Space demo for the DINO-Endo phase-recognition stack."
    return "Streamlit Hugging Face Space demo for DINO-Endo, AI-Endo, and V-JEPA2 with one active model loaded at a time."


def _inject_app_styles() -> None:
    st.markdown(
        """
        <style>
        /* Dark minimal fonts */
        @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;0,700;1,300;1,400&family=IBM+Plex+Mono:wght@300;400;500&family=Inter:wght@300;400;500;600&display=swap');

        /* Base Streamlit overrides — dark blue-black */
        .stApp, .main, .block-container {
            background-color: #06080a !important;
            background-image: none !important;
            color: #e8e6e3 !important;
        }

        .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
            max-width: 1400px;
            font-family: 'Inter', sans-serif;
            position: relative;
            z-index: 1;
        }

        /* Hide Streamlit branding */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}

        /* Particle constellation canvas */
        #particle-canvas {
            position: fixed;
            top: 0; left: 0;
            width: 100%; height: 100%;
            pointer-events: none;
            z-index: 0;
        }

        /* Gradient atmosphere blobs */
        .stApp::after {
            content: "";
            position: fixed;
            top: 0; left: 0; width: 100%; height: 100%;
            pointer-events: none;
            z-index: 0;
            background:
                radial-gradient(ellipse 600px 400px at 15% 25%, rgba(14, 165, 233, 0.06), transparent 70%),
                radial-gradient(ellipse 500px 600px at 85% 55%, rgba(16, 185, 129, 0.05), transparent 70%),
                radial-gradient(ellipse 450px 350px at 50% 85%, rgba(139, 92, 246, 0.04), transparent 70%);
            animation: blob-drift 30s ease-in-out infinite alternate;
        }
        @keyframes blob-drift {
            0%   { transform: translate(0, 0) scale(1); }
            33%  { transform: translate(30px, -20px) scale(1.05); }
            66%  { transform: translate(-25px, 25px) scale(0.98); }
            100% { transform: translate(15px, 10px) scale(1.02); }
        }

        /* Subtle grain overlay for texture */
        .stApp::before {
            content: "";
            position: fixed;
            top: 0; left: 0; width: 100%; height: 100%;
            pointer-events: none;
            z-index: 9999;
            opacity: 0.015;
            background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 400 400' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
        }

        /* Custom scrollbar — gradient thumb */
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb {
            background: linear-gradient(180deg, #0ea5e9, #10b981, #8b5cf6);
            border-radius: 0;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: linear-gradient(180deg, #0ea5e9, #10b981, #8b5cf6);
            opacity: 0.8;
        }

        /* Text selection — green tint */
        ::selection { background: rgba(16, 185, 129, 0.3); color: #f5f3ef; }
        ::-moz-selection { background: rgba(16, 185, 129, 0.3); color: #f5f3ef; }

        /* Keyframes */
        @keyframes fadeInUp {
            from { opacity: 0; transform: translateY(15px); }
            to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes fadeInLeft {
            from { opacity: 0; transform: translateX(-12px); }
            to   { opacity: 1; transform: translateX(0); }
        }
        @keyframes fadeIn {
            from { opacity: 0; }
            to   { opacity: 1; }
        }
        @keyframes gradient-shift {
            0%   { background-position: 0% 50%; }
            50%  { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }
        @keyframes breathe {
            0%, 100% { transform: scale(1); }
            50%      { transform: scale(1.005); }
        }
        @keyframes pulse-glow {
            0%, 100% { opacity: 0.3; }
            50%      { opacity: 0.6; }
        }

        /* Minimal button styling — gradient border on hover */
        .stButton > button {
            border-radius: 0 !important;
            font-weight: 500 !important;
            padding: 0.7rem 1.8rem !important;
            transition: all 0.3s ease !important;
            text-transform: uppercase !important;
            letter-spacing: 0.1em !important;
            font-family: 'IBM Plex Mono', monospace !important;
            font-size: 0.7rem !important;
            background: transparent !important;
            border: 1px solid rgba(255,255,255,0.12) !important;
            color: #d0cdc8 !important;
            position: relative;
        }

        .stButton > button:hover {
            border-color: transparent !important;
            background-clip: padding-box !important;
            background: rgba(255,255,255,0.04) !important;
            transform: translateY(-2px);
            box-shadow:
                0 0 20px rgba(14, 165, 233, 0.12),
                0 0 40px rgba(139, 92, 246, 0.06),
                inset 0 0 0 1px rgba(16, 185, 129, 0.3);
        }

        .stButton > button:active {
            transform: scale(0.98) translateY(0);
        }

        .stButton > button[kind="primary"] {
            background: rgba(255,255,255,0.06) !important;
            border: 1px solid rgba(255,255,255,0.18) !important;
        }

        .stButton > button[kind="secondary"] {
            background: transparent !important;
            border: 1px solid rgba(255,255,255,0.08) !important;
            color: #888 !important;
        }

        /* Cards — subtle borders with breathing + category glow */
        .hub-hero,
        .hub-card,
        .workspace-card,
        .project-card {
            border-radius: 0;
            border: 1px solid rgba(255, 255, 255, 0.06);
            background: rgba(255, 255, 255, 0.015);
            padding: 2.5rem;
            margin-bottom: 2rem;
            display: flex;
            flex-direction: column;
            transition: all 0.4s ease;
            animation: fadeInUp 0.8s ease both, breathe 6s ease-in-out infinite;
        }

        .hub-card:hover, .workspace-card:hover, .project-card:hover {
            border-color: rgba(255, 255, 255, 0.12);
            background: rgba(255, 255, 255, 0.03);
            transform: translateY(-2px);
            box-shadow: 0 0 30px rgba(14, 165, 233, 0.06), 0 0 60px rgba(139, 92, 246, 0.04);
        }

        /* Hero Section — minimal, no gradients */
        .hub-hero {
            padding: 4rem 3rem;
            margin-bottom: 2rem;
            background: rgba(255, 255, 255, 0.015);
            border: 1px solid rgba(255, 255, 255, 0.06);
            position: relative;
        }

        .hub-eyebrow {
            margin: 0 0 0.5rem 0;
            color: #666;
            font-size: 0.7rem;
            font-weight: 500;
            font-family: 'IBM Plex Mono', monospace;
            letter-spacing: 0.15em;
            text-transform: uppercase;
        }

        .hub-hero h1 {
            font-size: 3.5rem;
            font-weight: 300;
            letter-spacing: -0.02em;
            line-height: 1.05;
            margin: 0;
            color: #f5f3ef;
            font-family: 'Cormorant Garamond', serif;
        }

        .workspace-card h2,
        .hub-card h3,
        .project-card h3 {
            margin: 0.5rem 0 0.75rem 0;
            color: #e8e6e3;
            font-weight: 400;
            letter-spacing: -0.01em;
            font-family: 'Cormorant Garamond', serif;
            font-size: 1.6rem;
        }

        .hub-subtitle {
            margin-top: 1.5rem;
            max-width: 50rem;
            font-size: 1.05rem;
            color: #888;
            line-height: 1.7;
            font-weight: 300;
            font-family: 'Inter', sans-serif;
        }

        .workspace-copy,
        .hub-card p,
        .project-card p {
            color: #9a9590;
            line-height: 1.7;
            font-size: 0.95rem;
            margin-bottom: 1rem;
            font-family: 'Inter', sans-serif;
        }

        .hub-card li,
        .project-card li {
            color: #777;
            line-height: 1.7;
            font-size: 0.9rem;
            margin-bottom: 0.5rem;
        }

        .hub-chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.6rem;
            margin-top: 1.25rem;
        }

        .hub-chip,
        .hub-status,
        .category-badge {
            display: inline-flex;
            align-items: center;
            border-radius: 0;
            padding: 0.4rem 0.9rem;
            font-size: 0.7rem;
            font-weight: 400;
            letter-spacing: 0.05em;
            transition: all 0.3s ease;
            cursor: default;
            font-family: 'IBM Plex Mono', monospace;
            text-transform: uppercase;
        }

        .hub-chip {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.08);
            color: #888;
        }

        .hub-chip:hover {
            background: rgba(255, 255, 255, 0.06);
            border-color: rgba(255, 255, 255, 0.15);
        }

        .hub-status {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.08);
            color: #aaa;
            margin-bottom: 1rem;
        }

        .category-badge {
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(255, 255, 255, 0.06);
            color: #777;
            font-size: 0.65rem;
        }

        .project-icon {
            font-size: 1.8rem;
            margin-bottom: 0.5rem;
            opacity: 0.6;
        }

        .hub-card,
        .workspace-card,
        .project-card {
            padding: 2.5rem;
            height: 100%;
            display: flex;
            flex-direction: column;
            position: relative;
            overflow: hidden;
        }

        .hub-card::before,
        .project-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 2px;
            background: linear-gradient(90deg, #0ea5e9, #10b981, #8b5cf6);
            opacity: 0;
            transition: opacity 0.3s ease;
        }

        .hub-card:hover::before,
        .project-card:hover::before {
            opacity: 0.6;
        }

        /* Featured project ribbon — minimal */
        .featured-ribbon {
            position: absolute;
            top: 0;
            right: 0;
            background: rgba(255, 255, 255, 0.06);
            color: #aaa;
            font-size: 0.6rem;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.15em;
            padding: 0.4rem 1rem;
            z-index: 2;
            font-family: 'IBM Plex Mono', monospace;
        }

        /* Category accent — colored left border with pulse glow */
        .project-card[data-category="Medical AI"], .mb-card[data-category="Medical AI"] {
            border-left: 2px solid rgba(14, 165, 233, 0.4);
        }
        .project-card[data-category="Medical AI"]:hover, .mb-card[data-category="Medical AI"]:hover {
            box-shadow: 0 0 25px rgba(14, 165, 233, 0.12), 0 0 50px rgba(14, 165, 233, 0.06);
            border-left-color: rgba(14, 165, 233, 0.8);
        }
        .project-card[data-category="Traffic Safety"], .mb-card[data-category="Traffic Safety"] {
            border-left: 2px solid rgba(245, 158, 11, 0.4);
        }
        .project-card[data-category="Traffic Safety"]:hover, .mb-card[data-category="Traffic Safety"]:hover {
            box-shadow: 0 0 25px rgba(245, 158, 11, 0.12), 0 0 50px rgba(245, 158, 11, 0.06);
            border-left-color: rgba(245, 158, 11, 0.8);
        }
        .project-card[data-category="Quantum Computing"], .mb-card[data-category="Quantum Computing"] {
            border-left: 2px solid rgba(139, 92, 246, 0.4);
        }
        .project-card[data-category="Quantum Computing"]:hover, .mb-card[data-category="Quantum Computing"]:hover {
            box-shadow: 0 0 25px rgba(139, 92, 246, 0.12), 0 0 50px rgba(139, 92, 246, 0.06);
            border-left-color: rgba(139, 92, 246, 0.8);
        }
        .project-card[data-category="Interpretability"], .mb-card[data-category="Interpretability"] {
            border-left: 2px solid rgba(236, 72, 153, 0.4);
        }
        .project-card[data-category="Interpretability"]:hover, .mb-card[data-category="Interpretability"]:hover {
            box-shadow: 0 0 25px rgba(236, 72, 153, 0.12), 0 0 50px rgba(236, 72, 153, 0.06);
            border-left-color: rgba(236, 72, 153, 0.8);
        }
        .project-card[data-category="Robotics"], .mb-card[data-category="Robotics"] {
            border-left: 2px solid rgba(16, 185, 129, 0.4);
        }
        .project-card[data-category="Robotics"]:hover, .mb-card[data-category="Robotics"]:hover {
            box-shadow: 0 0 25px rgba(16, 185, 129, 0.12), 0 0 50px rgba(16, 185, 129, 0.06);
            border-left-color: rgba(16, 185, 129, 0.8);
        }
        .project-card[data-category="Model Optimization"], .mb-card[data-category="Model Optimization"] {
            border-left: 2px solid rgba(239, 68, 68, 0.4);
        }
        .project-card[data-category="Model Optimization"]:hover, .mb-card[data-category="Model Optimization"]:hover {
            box-shadow: 0 0 25px rgba(239, 68, 68, 0.12), 0 0 50px rgba(239, 68, 68, 0.06);
            border-left-color: rgba(239, 68, 68, 0.8);
        }

        .hub-card ul,
        .project-card ul {
            margin: 1rem 0 0 1.2rem;
            padding: 0;
            flex-grow: 1;
        }

        .workspace-card {
            margin: 0.5rem 0 1.5rem 0;
        }

        /* Project Grid Layout */
        .projects-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 2rem;
            margin-top: 2rem;
        }

        /* Category Filter */
        .category-filter {
            display: flex;
            flex-wrap: wrap;
            gap: 0.75rem;
            margin-bottom: 2rem;
            padding: 1rem;
            background: rgba(255, 255, 255, 0.015);
            border: 1px solid rgba(255, 255, 255, 0.05);
        }

        .filter-chip {
            padding: 0.5rem 1.25rem;
            border-radius: 0;
            border: 1px solid rgba(255, 255, 255, 0.08);
            background: rgba(255, 255, 255, 0.02);
            color: #777;
            font-size: 0.75rem;
            font-weight: 400;
            cursor: pointer;
            transition: all 0.3s ease;
            font-family: 'IBM Plex Mono', monospace;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .filter-chip:hover,
        .filter-chip.active {
            background: rgba(255, 255, 255, 0.05);
            border-color: rgba(255, 255, 255, 0.2);
            color: #ccc;
        }

        /* Stats Section — minimal */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 1.5rem;
            margin: 2rem 0;
        }

        .stat-card {
            padding: 1.5rem;
            border-radius: 0;
            background: rgba(255, 255, 255, 0.015);
            border: 1px solid rgba(255, 255, 255, 0.05);
            text-align: center;
            transition: all 0.3s ease;
        }

        .stat-card:hover {
            border-color: rgba(255, 255, 255, 0.1);
            background: rgba(255, 255, 255, 0.025);
        }

        .stat-number {
            font-size: 2.2rem;
            font-weight: 300;
            color: #f5f3ef;
            font-family: 'Cormorant Garamond', serif;
            letter-spacing: -0.02em;
        }

        .stat-label {
            color: #555;
            font-size: 0.65rem;
            text-transform: uppercase;
            letter-spacing: 0.15em;
            margin-top: 0.5rem;
            font-family: 'IBM Plex Mono', monospace;
        }

        /* Select box / input dark styling */
        .stSelectbox label, .stTextInput label, .stNumberInput label {
            color: #777 !important;
            font-family: 'IBM Plex Mono', monospace !important;
            font-size: 0.7rem !important;
            text-transform: uppercase;
            letter-spacing: 0.1em;
        }

        .stSlider p {
            color: #777 !important;
        }

        /* Expander styling */
        .streamlit-expanderHeader {
            background: rgba(255,255,255,0.015) !important;
            border: 1px solid rgba(255,255,255,0.05) !important;
            color: #aaa !important;
            font-family: 'Cormorant Garamond', serif !important;
            font-size: 1.1rem !important;
        }

        .streamlit-expanderContent {
            background: transparent !important;
            border: 1px solid rgba(255,255,255,0.05) !important;
            border-top: none !important;
        }

        /* Code block dark */
        .stCodeBlock {
            background: rgba(255,255,255,0.02) !important;
            border: 1px solid rgba(255,255,255,0.05) !important;
        }

        /* Metric styling */
        [data-testid="stMetricValue"] {
            color: #f5f3ef !important;
            font-family: 'Cormorant Garamond', serif !important;
            font-size: 1.8rem !important;
            font-weight: 300 !important;
        }
        [data-testid="stMetricLabel"] {
            color: #555 !important;
            font-family: 'IBM Plex Mono', monospace !important;
            font-size: 0.65rem !important;
            text-transform: uppercase;
            letter-spacing: 0.1em;
        }

        /* Progress bar */
        .stProgress > div > div {
            background-color: rgba(255,255,255,0.1) !important;
        }
        .stProgress > div > div > div {
            background-color: #666 !important;
        }

        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {
            border-bottom: 1px solid rgba(255,255,255,0.06) !important;
            gap: 0 !important;
        }
        .stTabs [data-baseweb="tab"] {
            color: #555 !important;
            font-family: 'IBM Plex Mono', monospace !important;
            font-size: 0.7rem !important;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            border-radius: 0 !important;
            border: none !important;
            border-bottom: 2px solid transparent !important;
            padding: 0.8rem 1.2rem !important;
        }
        .stTabs [aria-selected="true"] {
            color: #e8e6e3 !important;
            border-bottom: 2px solid rgba(255,255,255,0.2) !important;
        }

        /* Responsive adjustments */
        @media (max-width: 768px) {
            .hub-hero h1 {
                font-size: 2.2rem;
            }
            .hub-hero {
                padding: 2rem;
            }
            .projects-grid {
                grid-template-columns: 1fr;
            }
        }
        </style>
        <canvas id="particle-canvas"></canvas>
        <script>
        (function() {{
            const canvas = document.getElementById('particle-canvas');
            if (!canvas) return;
            const ctx = canvas.getContext('2d');
            let particles = [];
            let mouse = {{ x: -1000, y: -1000 }};
            const colors = ['rgba(14,165,233,', 'rgba(16,185,129,', 'rgba(139,92,246,'];
            const PARTICLE_COUNT = 50;
            const MAX_DIST = 130;
            const MOUSE_DIST = 150;

            function resize() {{
                canvas.width = window.innerWidth;
                canvas.height = window.innerHeight;
            }}

            function initParticles() {{
                particles = [];
                for (let i = 0; i < PARTICLE_COUNT; i++) {{
                    particles.push({{
                        x: Math.random() * canvas.width,
                        y: Math.random() * canvas.height,
                        vx: (Math.random() - 0.5) * 0.3,
                        vy: (Math.random() - 0.5) * 0.3,
                        r: Math.random() * 1.5 + 0.5,
                        ci: Math.floor(Math.random() * colors.length),
                        opacity: Math.random() * 0.15 + 0.08
                    }});
                }}
            }}

            function animate() {{
                ctx.clearRect(0, 0, canvas.width, canvas.height);

                for (let i = 0; i < particles.length; i++) {{
                    const p = particles[i];
                    // Mouse attraction
                    const dx = mouse.x - p.x;
                    const dy = mouse.y - p.y;
                    const md = Math.sqrt(dx * dx + dy * dy);
                    if (md < MOUSE_DIST) {{
                        const force = (MOUSE_DIST - md) / MOUSE_DIST * 0.02;
                        p.vx += (dx / md) * force;
                        p.vy += (dy / md) * force;
                    }}

                    // Damping
                    p.vx *= 0.99;
                    p.vy *= 0.99;

                    // Elongation detail — stretch when moving fast
                    const speed = Math.sqrt(p.vx * p.vx + p.vy * p.vy);
                    const stretch = Math.min(speed * 3, 3);

                    p.x += p.vx;
                    p.y += p.vy;

                    // Wrap edges
                    if (p.x < 0) p.x = canvas.width;
                    if (p.x > canvas.width) p.x = 0;
                    if (p.y < 0) p.y = canvas.height;
                    if (p.y > canvas.height) p.y = 0;

                    // Draw particle (stretched ellipse)
                    ctx.beginPath();
                    ctx.ellipse(p.x, p.y, p.r + stretch, p.r, 0, 0, Math.PI * 2);
                    ctx.fillStyle = colors[p.ci] + p.opacity + ')';
                    ctx.fill();

                    // Draw connections
                    for (let j = i + 1; j < particles.length; j++) {{
                        const p2 = particles[j];
                        const ddx = p.x - p2.x;
                        const ddy = p.y - p2.y;
                        const dd = Math.sqrt(ddx * ddx + ddy * ddy);
                        if (dd < MAX_DIST) {{
                            const lineOpacity = (1 - dd / MAX_DIST) * 0.08;
                            ctx.beginPath();
                            ctx.moveTo(p.x, p.y);
                            ctx.lineTo(p2.x, p2.y);
                            ctx.strokeStyle = colors[p.ci] + lineOpacity + ')';
                            ctx.lineWidth = 0.5;
                            ctx.stroke();
                        }}
                    }}
                }}
                requestAnimationFrame(animate);
            }}

            window.addEventListener('resize', () => {{ resize(); initParticles(); }});
            window.addEventListener('mousemove', (e) => {{ mouse.x = e.clientX; mouse.y = e.clientY; }});
            window.addEventListener('mouseout', () => {{ mouse.x = -1000; mouse.y = -1000; }});

            resize();
            initParticles();
            animate();
        }})();
        </script>
        """,
        unsafe_allow_html=True,
    )


def _render_hub_chips(labels: list[str] | tuple[str, ...]) -> str:
    return "".join(f'<span class="hub-chip">{label}</span>' for label in labels)

def _render_category_badge(category: str, color: str) -> str:
    return f'<span class="category-badge" style="border-color: {color}40; color: {color};">{category}</span>'

def _render_project_icon(icon: str) -> str:
    return f'<div class="project-icon">{icon}</div>'


def _render_project_hub(enabled_model_keys: list[str]) -> None:
    featured = HOSTED_PROJECTS[0]
    enabled_labels = [_model_option_label(key) for key in enabled_model_keys]
    availability_map = _model_availability_map(enabled_model_keys)
    ready_count = sum(1 for availability in availability_map.values() if availability.is_available)
    blocked_count = len(enabled_model_keys) - ready_count
    total_projects = len(HOSTED_PROJECTS)
    live_projects = sum(1 for p in HOSTED_PROJECTS if p.status == "Live now")
    integrated_projects = sum(1 for p in HOSTED_PROJECTS if p.status == "Integrated")
    categories = len(set(p.category for p in HOSTED_PROJECTS))

    # Dark, minimal hero
    st.markdown(
        f"""
        <style>
        .hub-hero-dark {{
            padding: 4rem 2rem;
            margin-bottom: 3rem;
            border: 1px solid rgba(255,255,255,0.05);
            background: rgba(255,255,255,0.01);
            position: relative;
            overflow: hidden;
            animation: fadeInUp 0.8s ease both;
        }}
        /* Angular accent line — Persona 5 central line */
        .hub-hero-dark::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 3px;
            height: 100%;
            background: linear-gradient(180deg, #0ea5e9, #10b981, #8b5cf6);
            opacity: 0.5;
        }}
        /* Diagonal corner accent */
        .hub-hero-dark::after {{
            content: '';
            position: absolute;
            top: -20px;
            right: -20px;
            width: 80px;
            height: 1px;
            background: linear-gradient(90deg, transparent, rgba(16, 185, 129, 0.3));
            transform: rotate(-45deg);
            transform-origin: top right;
        }}
        .hub-hero-dark .eyebrow {{
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.6rem;
            color: rgba(16, 185, 129, 0.6);
            letter-spacing: 0.25em;
            text-transform: uppercase;
            margin-bottom: 1.5rem;
        }}
        .hub-hero-dark h1 {{
            font-family: 'Cormorant Garamond', serif;
            font-size: clamp(2.5rem, 6vw, 4rem);
            font-weight: 300;
            line-height: 1;
            letter-spacing: -0.02em;
            margin: 0;
            background: linear-gradient(90deg, #0ea5e9, #10b981, #8b5cf6, #0ea5e9);
            background-size: 200% auto;
            -webkit-background-clip: text;
            background-clip: text;
            -webkit-text-fill-color: transparent;
            animation: gradient-shift 8s ease infinite;
        }}
        .hub-hero-dark .subtitle {{
            font-family: 'Inter', sans-serif;
            font-size: 1rem;
            color: #777;
            line-height: 1.7;
            max-width: 520px;
            margin-top: 1.5rem;
        }}
        .hub-hero-dark .meta-line {{
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.6rem;
            color: #444;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            margin-top: 2rem;
        }}
        .dark-stat {{
            text-align: center;
            padding: 1.5rem 1rem;
            border: 1px solid rgba(255,255,255,0.04);
            background: rgba(255,255,255,0.01);
        }}
        .dark-stat .num {{
            font-family: 'Cormorant Garamond', serif;
            font-size: 2rem;
            font-weight: 300;
            color: #f5f3ef;
            line-height: 1;
        }}
        .dark-stat .label {{
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.6rem;
            color: #555;
            letter-spacing: 0.15em;
            text-transform: uppercase;
            margin-top: 0.6rem;
        }}
        </style>
        <div class="hub-hero-dark">
            <div class="eyebrow">gyanateet dutta / leeds</div>
            <h1>{SPACE_TITLE}</h1>
            <p class="subtitle">
                I'm a Master's student at Leeds working on self-supervised vision for surgical phase recognition.
                This Space hosts demos from my projects — ML for quantum error correction, vision-language-action
                for robotics, and model compression.
            </p>
            <div class="meta-line">6 demos &nbsp;&bull;&nbsp; surgical vision &nbsp;&bull;&nbsp; QEC decoding &nbsp;&bull;&nbsp; robotics &nbsp;&bull;&nbsp; compression</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Simple tagline instead of stats grid
    st.markdown(
        """
        <div style="margin: 1.5rem 0; opacity: 0.6; font-size: 0.85rem;">
            6 demos &nbsp;&bull;&nbsp; surgical vision, QEC decoding, robotics, compression
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Featured + ecosystem — cleaner, two column
    left_col, right_col = st.columns([1.6, 1.4], gap="large")
    with left_col:
        highlights_html = "".join(f"<li>{item}</li>" for item in featured.highlights)
        st.markdown(
            f"""
            <section class="hub-card" style="border-left: 1px solid rgba(255,255,255,0.08);">
                <div class="featured-ribbon">featured</div>
                <span class="hub-status">{featured.status}</span>
                {_render_category_badge(featured.category, featured.color)}
                {_render_project_icon(featured.icon)}
                <h3>{featured.title}</h3>
                <p>{featured.summary}</p>
                <div class="hub-chip-row">{_render_hub_chips(featured.tags)}</div>
                <ul>{highlights_html}</ul>
            </section>
            """,
            unsafe_allow_html=True,
        )

    with right_col:
        st.markdown(
            """
            <section class="hub-card">
                <span class="hub-status">about</span>
                <div style="font-size:1.4rem; opacity:0.5; margin-bottom:0.5rem;">&#9881;</div>
                <h3>About</h3>
                <p>
                    I use ML as a tool across problems — surgical video understanding, quantum error correction
                    decoding, and robotic perception. Currently interning in vision research at Leeds.
                    Qiskit Advocate, ISBI 2026.
                </p>
                <ul>
                    <li><a href="https://github.com/Ryukijano" target="_blank">GitHub</a></li>
                    <li><a href="https://huggingface.co/Ryukijano" target="_blank">Hugging Face</a></li>
                    <li><a href="https://ryukijano.github.io" target="_blank">Website</a></li>
                </ul>
            </section>
            """,
            unsafe_allow_html=True,
        )

    action_cols = st.columns([1.2, 1.0, 1.0], gap="medium")
    if action_cols[0].button("Open Workspace", key="open-featured-workspace", use_container_width=True):
        _navigate_to_page("workspace")
    if action_cols[1].button("Browse Projects", key="open-project-pages", use_container_width=True):
        _navigate_to_page("projects")
    action_cols[2].download_button(
        "Download Summary",
        json.dumps(
            {
                "title": SPACE_TITLE,
                "pages": list(PORTFOLIO_PAGE_LABELS.values()),
                "projects": [
                    {
                        "title": project.title,
                        "status": project.status,
                        "category": project.category,
                        "tags": list(project.tags)
                    }
                    for project in HOSTED_PROJECTS
                ],
            },
            indent=2,
        ).encode("utf-8"),
        file_name="project_summary.json",
        mime="application/json",
        use_container_width=True,
    )

    unavailable_keys = [model_key for model_key in enabled_model_keys if not availability_map[model_key].is_available]
    if unavailable_keys:
        unavailable_labels = ", ".join(_model_option_label(model_key) for model_key in unavailable_keys)
        st.warning(
            f"Some models are not currently loadable in the public Space: {unavailable_labels}. "
            "Open the workspace page for targeted status details."
        )


def _render_projects_page() -> None:
    # Minimal project page — clean, dark
    st.markdown(
        """
        <style>
        .moodboard-projects {
            position: relative;
            max-width: 1200px;
            margin: 0 auto;
            padding-bottom: 4rem;
        }
        .mb-section-label {
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.6rem;
            color: rgba(16, 185, 129, 0.5);
            letter-spacing: 0.2em;
            text-transform: uppercase;
            margin-bottom: 2rem;
        }
        .mb-title {
            font-family: 'Cormorant Garamond', serif;
            font-size: clamp(2rem, 5vw, 3.5rem);
            font-weight: 300;
            line-height: 1;
            letter-spacing: -0.02em;
            margin: 0 0 1rem 0;
            background: linear-gradient(90deg, #0ea5e9, #10b981, #8b5cf6, #0ea5e9);
            background-size: 200% auto;
            -webkit-background-clip: text;
            background-clip: text;
            -webkit-text-fill-color: transparent;
            animation: gradient-shift 8s ease infinite;
        }
        .mb-subtitle {
            font-family: 'Inter', sans-serif;
            font-size: 0.95rem;
            color: #777;
            line-height: 1.7;
            max-width: 480px;
            margin-bottom: 3rem;
        }
        .mb-card {
            border: 1px solid rgba(255,255,255,0.05);
            background: rgba(255,255,255,0.01);
            padding: 1.8rem;
            transition: all 0.3s ease;
            position: relative;
            animation: fadeInUp 0.6s ease both;
        }
        .mb-card:hover {
            border-color: rgba(255,255,255,0.1);
            background: rgba(255,255,255,0.025);
            transform: translateY(-2px);
        }
        .mb-card::after {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 2px;
            background: linear-gradient(90deg, #0ea5e9, #10b981, #8b5cf6);
            opacity: 0;
            transition: opacity 0.3s ease;
        }
        .mb-card:hover::after {
            opacity: 0.5;
        }
        .mb-card-num {
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.55rem;
            color: #333;
            letter-spacing: 0.1em;
            margin-bottom: 0.8rem;
        }
        .mb-card-title {
            font-family: 'Cormorant Garamond', serif;
            font-size: 1.3rem;
            font-weight: 400;
            color: #ddd;
            margin: 0 0 0.6rem 0;
            line-height: 1.2;
        }
        .mb-card-body {
            font-family: 'Inter', sans-serif;
            font-size: 0.85rem;
            color: #777;
            line-height: 1.6;
            margin-bottom: 1rem;
        }
        .mb-card-meta {
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.6rem;
            color: #444;
            text-transform: uppercase;
            letter-spacing: 0.1em;
        }
        .mb-divider {
            width: 40px;
            height: 1px;
            background: repeating-linear-gradient(90deg, #333 0, #333 2px, transparent 2px, transparent 4px);
            margin: 2rem 0;
        }
        .mb-scattered-note {
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.6rem;
            color: #333;
            letter-spacing: 0.15em;
            text-transform: uppercase;
            transform: rotate(-2deg);
            display: inline-block;
            margin: 1rem 0;
        }
        </style>
        <div class="moodboard-projects">
        <div class="mb-section-label">projects</div>
        <h2 class="mb-title">Projects</h2>
        <p class="mb-subtitle">
            ML demos across surgical vision, quantum error correction, robotics, and model compression.
        </p>
        <div class="mb-divider"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Category filter
    categories = ["All"] + sorted(set(p.category for p in HOSTED_PROJECTS))
    selected_category = st.selectbox("Filter by category", categories, key="category-filter")
    filtered_projects = HOSTED_PROJECTS if selected_category == "All" else [p for p in HOSTED_PROJECTS if p.category == selected_category]

    # Responsive grid layout
    layout_pattern = [
        [2, 1],   # first row: wide + narrow
        [1, 2],   # second row: narrow + wide
        [1, 1, 1], # third row: three equal
        [3],      # fourth row: full width
        [1, 2],   # etc.
    ]

    proj_idx = 0
    pattern_idx = 0
    while proj_idx < len(filtered_projects):
        pattern = layout_pattern[pattern_idx % len(layout_pattern)]
        row_projects = filtered_projects[proj_idx:proj_idx + len(pattern)]
        if not row_projects:
            break

        cols = st.columns(pattern[:len(row_projects)])
        for col, project in zip(cols, row_projects):
            with col:
                num = f"{proj_idx + 1:02d}"
                st.markdown(
                    f"""
                    <div class="mb-card" data-category="{project.category}">
                        <div class="mb-card-num">{num} / {project.category.upper()}</div>
                        <div class="mb-card-title">{project.icon} {project.title}</div>
                        <div class="mb-card-body">{project.summary}</div>
                        <div class="mb-card-meta">status: {project.status} &nbsp;&bull;&nbsp; {len(project.tags)} tags</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if project.key == HOSTED_PROJECTS[0].key:
                    if st.button("Open Workspace", key=f"open-page-{project.key}", use_container_width=True):
                        _navigate_to_page("workspace")
                elif project.status == "Live now":
                    label = "Open " + project.title.split()[0]
                    if st.button(label, key=f"open-live-{project.key}", use_container_width=True):
                        if project.key == "cosmos-sentinel":
                            _navigate_to_page("cosmos_sentinel")
                        elif project.key == "syndrome-net":
                            _navigate_to_page("syndrome_net")
                        elif project.key == "enterprise_dashboard":
                            _navigate_to_page("enterprise_dashboard")
                else:
                    st.button("View Details", key=f"details-{project.key}", use_container_width=True)
            proj_idx += 1
        pattern_idx += 1

    st.markdown(
        """
        <div class="moodboard-projects" style="text-align:center; margin-top:3rem;">
            <div class="mb-scattered-note">&nbsp;</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_technical_page() -> None:
    st.markdown(
        """
        <style>
        .tech-hero {
            padding: 3rem 2rem;
            margin-bottom: 2rem;
            border: 1px solid rgba(255,255,255,0.05);
            background: rgba(255,255,255,0.01);
        }
        .tech-hero .eyebrow {
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.6rem;
            color: #444;
            letter-spacing: 0.25em;
            text-transform: uppercase;
            margin-bottom: 1rem;
        }
        .tech-hero h2 {
            font-family: 'Cormorant Garamond', serif;
            font-size: 2rem;
            font-weight: 300;
            color: #f5f3ef;
            margin: 0 0 0.8rem 0;
        }
        .tech-hero p {
            font-family: 'Inter', sans-serif;
            font-size: 0.9rem;
            color: #777;
            line-height: 1.6;
            max-width: 480px;
        }
        .tech-section-label {
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.6rem;
            color: #444;
            letter-spacing: 0.2em;
            text-transform: uppercase;
            margin: 2rem 0 1rem 0;
        }
        </style>
        <div class="tech-hero">
            <div class="eyebrow">technical specifications</div>
            <h2>Architecture & Hardware</h2>
            <p>Model files, inference requirements, and the stack behind each project.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # GPU memory monitoring
    if torch.cuda.is_available():
        gpu_count = torch.cuda.device_count()
        st.markdown('<div class="tech-section-label">system resources</div>', unsafe_allow_html=True)
        st.write(f"GPU Devices: {gpu_count}")
        for i in range(gpu_count):
            gpu_name = torch.cuda.get_device_name(i)
            gpu_memory_total = torch.cuda.get_device_properties(i).total_memory / 1024**3
            gpu_memory_reserved = torch.cuda.memory_reserved(i) / 1024**3
            gpu_memory_free = gpu_memory_total - gpu_memory_reserved
            c1, c2, c3 = st.columns(3)
            c1.metric("GPU", gpu_name[:24])
            c2.metric("VRAM Total", f"{gpu_memory_total:.1f} GB")
            c3.metric("VRAM Free", f"{gpu_memory_free:.1f} GB")
    else:
        st.info("CUDA is not available. Running in CPU-only mode.")

    # Model manager status
    manager = _get_model_manager()
    status = manager.status()
    st.markdown('<div class="tech-section-label">model manager</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    c1.metric("Active", status.active_model_label or "None")
    c2.metric("Loaded", "Yes" if status.is_loaded else "No")
    if status.last_error:
        st.error(f"Last Error: {status.last_error}")
    if st.button("force GPU cleanup", key="force-cleanup"):
        manager.unload_model()
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        st.success("GPU memory cleaned up.")
        st.rerun()

    # Technical showcase for each project
    st.markdown('<div class="tech-section-label">project details</div>', unsafe_allow_html=True)
    for project in HOSTED_PROJECTS:
        with st.expander(f"{project.icon} {project.title}", expanded=False):
            col1, col2 = st.columns([2, 1])
            with col1:
                st.markdown(f"**{project.title}**")
                st.markdown(f"*{project.status}* · {project.category}")
                st.markdown(project.summary)
                if project.model_link:
                    st.markdown(f"[repository]({project.model_link})")
                st.markdown("**Stack**")
                if project.architecture:
                    st.markdown(f"`{project.architecture}`")
                if project.framework:
                    st.markdown(f"`{project.framework}`")
                if project.model_size:
                    st.markdown(f"`{project.model_size}`")
                if project.hardware_requirements:
                    st.markdown(f"`{project.hardware_requirements}`")
            with col2:
                st.markdown("**Features**")
                for hl in project.highlights:
                    st.markdown(f"- {hl}")
                if project.performance_metrics:
                    st.markdown("**Metrics**")
                    for metric, value in project.performance_metrics.items():
                        st.markdown(f"{metric}: {value}")
                if project.model_link:
                    if st.button("Visit Repo", key=f"visit-{project.key}"):
                        import webbrowser
                        webbrowser.open(project.model_link)

    # Common requirements
    st.markdown('<div class="tech-section-label">common dependencies</div>', unsafe_allow_html=True)
    st.code("""
python >= 3.10
torch >= 2.0.0
torchvision >= 0.15.0
numpy >= 1.24.0
pillow >= 10.0.0
CUDA >= 11.8
    """, language="bash")


def _render_workspace_header(enabled_model_keys: list[str], model_key: str) -> None:
    selected_label = _model_option_label(model_key)
    selection_note = (
        "Use the model slider to move between DINO-Endo, AI-Endo, and V-JEPA2. "
        "Only one model stays loaded at a time so the Space remains responsive on shared GPU hardware, and video runs now "
        "produce an annotated playback clip with the phase HUD burned directly onto the frames."
    )
    st.markdown(
        f"""
        <section class="workspace-card">
            <p class="hub-eyebrow">Featured project</p>
            <h2>{FEATURED_PROJECT_TITLE}</h2>
            <p class="workspace-copy">
                {selection_note}
            </p>
            <div class="hub-chip-row">
                {_render_hub_chips(tuple(_model_option_label(key) for key in enabled_model_keys))}
                <span class="hub-chip">Selected: {selected_label}</span>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_model_availability_sidebar(enabled_model_keys: list[str], availability_map: dict[str, object]) -> None:
    st.sidebar.markdown("### Model availability")
    if st.sidebar.button("Refresh model status", key="refresh-model-availability", use_container_width=True):
        clear_model_availability_cache()
        st.rerun()

    for model_key in enabled_model_keys:
        availability = availability_map[model_key]
        label = _model_option_label(model_key)
        if availability.status == "ready":
            st.sidebar.success(f"{label}: ready from local cache")
        elif availability.status == "downloadable":
            st.sidebar.info(f"{label}: ready to download on first use")
        else:
            st.sidebar.warning(f"{label}: unavailable")
            st.sidebar.caption(availability.message)


def _render_unavailable_model_notice(enabled_model_keys: list[str], availability_map: dict[str, object]) -> None:
    unavailable_keys = [model_key for model_key in enabled_model_keys if not availability_map[model_key].is_available]
    if not unavailable_keys:
        return

    for model_key in unavailable_keys:
        availability = availability_map[model_key]
        st.warning(f"{_model_option_label(model_key)} is unavailable: {availability.message}")


def _resolve_model_selection(enabled_model_keys: list[str], default_model_key: str) -> tuple[str | None, str]:
    previous_selected_model_key = st.session_state.get(SELECTED_MODEL_STATE_KEY)
    current_slider_value = st.session_state.get(MODEL_SLIDER_KEY)
    if current_slider_value not in enabled_model_keys:
        st.session_state[MODEL_SLIDER_KEY] = default_model_key

    if len(enabled_model_keys) == 1:
        model_key = enabled_model_keys[0]
        st.session_state[MODEL_SLIDER_KEY] = model_key
        return previous_selected_model_key, model_key

    model_key = st.select_slider(
        "Project model slider",
        options=enabled_model_keys,
        key=MODEL_SLIDER_KEY,
        format_func=_model_option_label,
        help="Prominent model-family slider for the DINO-Endo project workspace.",
    )
    return previous_selected_model_key, model_key


def _get_model_manager() -> SpaceModelManager:
    manager = st.session_state.get("model_manager")
    if manager is None:
        manager = SpaceModelManager()
        st.session_state["model_manager"] = manager
    return manager


def _current_portfolio_page() -> str:
    page_key = st.session_state.get(PORTFOLIO_PAGE_STATE_KEY, "intro")
    if page_key not in PORTFOLIO_PAGE_LABELS:
        page_key = "intro"
        st.session_state[PORTFOLIO_PAGE_STATE_KEY] = page_key
    return page_key


def _navigate_to_page(page_key: str) -> None:
    if page_key not in PORTFOLIO_PAGE_LABELS:
        raise RuntimeError(f"Unsupported portfolio page '{page_key}'")
    
    # GPU memory optimization: unload models when switching away from workspace
    current_page = _current_portfolio_page()
    if current_page == "workspace" and page_key != "workspace":
        manager = _get_model_manager()
        manager.unload_model()
        _clear_video_stage()
        _clear_video_analysis()
    
    st.session_state[PORTFOLIO_PAGE_STATE_KEY] = page_key
    st.rerun()


def _render_page_navigation() -> str:
    current_page = _current_portfolio_page()

    # Angular navigation styling — Persona kinetic energy
    st.markdown("""
    <style>
    .minimal-nav {
        border: 1px solid rgba(255, 255, 255, 0.06);
        padding: 1.5rem 1.5rem 1rem 1.5rem;
        margin-bottom: 2rem;
        background: rgba(255, 255, 255, 0.01);
        animation: fadeIn 0.6s ease both;
    }
    .minimal-nav-title {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.65rem;
        color: rgba(16, 185, 129, 0.5);
        text-transform: uppercase;
        letter-spacing: 0.25em;
        margin-bottom: 1.2rem;
    }
    .nav-track {
        display: flex;
        flex-wrap: wrap;
        gap: 0.4rem;
    }
    .nav-item {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.65rem;
        color: #555;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        padding: 0.5rem 0.9rem;
        border: 1px solid rgba(255,255,255,0.06);
        background: rgba(255,255,255,0.015);
        transition: all 0.25s ease;
        cursor: pointer;
        text-align: center;
        white-space: nowrap;
        transform: skewX(-1deg);
        animation: fadeInLeft 0.5s ease both;
    }
    .nav-item:hover {
        border-color: rgba(16, 185, 129, 0.3);
        color: #aaa;
        background: rgba(255,255,255,0.03);
        transform: skewX(-1deg) translateX(2px);
    }
    .nav-item.active {
        border-color: transparent;
        color: #e8e6e3;
        background: rgba(255,255,255,0.04);
        box-shadow: inset 0 0 0 1px rgba(14, 165, 233, 0.3), 0 0 15px rgba(16, 185, 129, 0.08);
    }
    .page-summary {
        font-family: 'IBM Plex Mono', monospace;
        color: #444;
        font-size: 0.7rem;
        letter-spacing: 0.05em;
        margin-top: 1.2rem;
        padding-top: 1rem;
        border-top: 1px solid rgba(255,255,255,0.04);
        text-transform: uppercase;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="minimal-nav">', unsafe_allow_html=True)
    st.markdown('<div class="minimal-nav-title">navigation</div>', unsafe_allow_html=True)

    # Render nav items in a grid using Streamlit columns
    nav_items = list(PORTFOLIO_PAGE_LABELS.items())
    cols_per_row = 6
    for i in range(0, len(nav_items), cols_per_row):
        row_items = nav_items[i:i+cols_per_row]
        nav_cols = st.columns(len(row_items))
        for col, (page_key, label) in zip(nav_cols, row_items):
            active_class = "active" if page_key == current_page else ""
            st.markdown(f'<div class="nav-item {active_class}">{label}</div>', unsafe_allow_html=True)
            if col.button(label, key=f"portfolio-nav-{page_key}", use_container_width=True):
                if page_key != current_page:
                    _navigate_to_page(page_key)

    st.markdown(
        f'<div class="page-summary">{PORTFOLIO_PAGE_SUMMARIES.get(current_page, "")}</div>',
        unsafe_allow_html=True,
    )
    st.markdown('</div>', unsafe_allow_html=True)

    return current_page


def _clear_video_analysis() -> None:
    analysis_state = st.session_state.pop(VIDEO_ANALYSIS_STATE_KEY, None)
    if not analysis_state:
        return

    annotated_video_path = analysis_state.get("annotated_video_path")
    if annotated_video_path:
        Path(annotated_video_path).unlink(missing_ok=True)


def _clear_video_stage() -> None:
    _clear_video_analysis()
    temp_path = st.session_state.pop("staged_video_path", None)
    if temp_path is not None:
        Path(temp_path).unlink(missing_ok=True)
    st.session_state.pop("staged_video_signature", None)
    st.session_state.pop("staged_video_meta", None)


def _prepare_staged_video(uploaded_file):
    upload_size_bytes = get_upload_size_bytes(uploaded_file)
    signature = (
        getattr(uploaded_file, "name", "upload"),
        upload_size_bytes,
        getattr(uploaded_file, "type", ""),
    )
    staged_path = st.session_state.get("staged_video_path")
    staged_signature = st.session_state.get("staged_video_signature")
    if staged_signature == signature and staged_path is not None and Path(staged_path).exists():
        return Path(staged_path), st.session_state["staged_video_meta"]

    _clear_video_stage()
    temp_path = spool_uploaded_video(uploaded_file)
    try:
        meta = probe_video_info(temp_path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    st.session_state["staged_video_signature"] = signature
    st.session_state["staged_video_path"] = str(temp_path)
    st.session_state["staged_video_meta"] = meta
    return temp_path, meta


def _video_analysis_signature(
    staged_signature: tuple[str, int, str] | None, model_key: str, frame_stride: int, max_frames: int
) -> tuple:
    return staged_signature, model_key, frame_stride, max_frames


def _records_to_frame(records):
    if not records:
        return pd.DataFrame(columns=["frame_index", "timestamp_sec", "phase", "confidence"])
    return pd.DataFrame.from_records(records)


def _download_payloads(df: pd.DataFrame):
    json_payload = df.to_json(orient="records", indent=2).encode("utf-8")
    csv_payload = df.to_csv(index=False).encode("utf-8")
    return json_payload, csv_payload


def _get_explainability_spec(manager: SpaceModelManager, model_key: str) -> ExplainabilitySpec:
    predictor = manager.get_loaded_predictor(model_key)
    if predictor is not None and hasattr(predictor, "get_explainability_spec"):
        return predictor.get_explainability_spec()
    return FALLBACK_EXPLAINABILITY_SPECS[model_key]


def _build_explainability_config(manager: SpaceModelManager, model_key: str):
    spec = _get_explainability_spec(manager, model_key)
    st.sidebar.markdown("### Explainability")
    enabled = st.sidebar.toggle(
        "Enable live encoder/decoder maps",
        value=False,
        help="Shows encoder heatmaps and decoder temporal strips on every processed frame. Leave this off if you want the fastest video analysis path.",
    )
    config = {"enabled": enabled}
    if not enabled:
        return config, spec

    st.sidebar.caption(f"Encoder view: {spec.encoder_label}")
    st.sidebar.caption(f"Decoder view: {spec.decoder_label}")
    if spec.encoder_mode == "attention" and spec.encoder_layer_count > 0 and spec.encoder_head_count > 0:
        default_layer = spec.encoder_layer_count - 1
        config["encoder_layer"] = st.sidebar.slider(
            "Encoder layer",
            min_value=1,
            max_value=spec.encoder_layer_count,
            value=default_layer + 1,
            key=f"explainability-layer-{model_key}",
        ) - 1
        config["encoder_head"] = st.sidebar.slider(
            "Encoder head",
            min_value=1,
            max_value=spec.encoder_head_count,
            value=1,
            key=f"explainability-head-{model_key}",
        ) - 1
    else:
        st.sidebar.info("This model uses a proxy encoder overlay instead of true encoder attention.")

    st.sidebar.caption("Decoder strips are rendered as temporal heat strips rather than projected back onto the frame.")
    return config, spec


def _render_explainability_panel(target, payload: dict | None, *, enabled: bool, spec: ExplainabilitySpec, title: str) -> None:
    with target.container():
        st.markdown(f"### {title}")
        if not enabled:
            st.caption("Turn on the explainability toggle in the sidebar to inspect encoder heatmaps and decoder temporal strips.")
            return

        st.caption(f"Encoder default: {spec.encoder_label}")
        st.caption(f"Decoder default: {spec.decoder_label}")
        if payload is None:
            st.info("Run image or video inference to populate this live explainability panel.")
            return

        layer_index = payload.get("encoder_layer")
        head_index = payload.get("encoder_head")
        encoder_caption = f"{payload['encoder_label']} ({payload['encoder_kind']})"
        if layer_index is not None and head_index is not None:
            encoder_caption += f" · layer {int(layer_index) + 1}, head {int(head_index) + 1}"
        st.caption(encoder_caption)
        st.image(payload["encoder_visualization"], use_container_width=True)

        st.caption(f"{payload['decoder_label']} ({payload['decoder_kind']})")
        st.image(payload["decoder_visualization"], use_container_width=True)

        notes = payload.get("notes")
        if notes:
            st.caption(notes)


def _analyse_video(
    video_path: str | Path,
    predictor,
    frame_stride: int,
    max_frames: int,
    *,
    video_info: dict | None = None,
    model_label: str,
    explainability_config: dict | None = None,
    explainability_callback=None,
):
    temp_path = Path(video_path)
    capture = cv2.VideoCapture(str(temp_path))
    if not capture.isOpened():
        raise RuntimeError("Unable to open uploaded video")

    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or (video_info or {}).get("frame_count") or 0)
    fps = float(capture.get(cv2.CAP_PROP_FPS) or (video_info or {}).get("fps") or 0.0)
    output_fps = fps if fps > 0 else float((video_info or {}).get("fps") or 24.0)
    progress = st.progress(0)
    status = st.empty()

    predictor.reset_state()
    records = []
    processed = 0
    rendered_frames = 0
    frame_index = 0
    truncated = False
    explain_enabled = bool(explainability_config and explainability_config.get("enabled"))
    latest_overlay_result = {
        "phase": "unknown",
        "confidence": 0.0,
    }
    overlay_writer = None
    overlay_intermediate_path = None
    overlay_warning = None
    analysis_failed = False

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break

            sampled_frame = frame_index % frame_stride == 0

            if sampled_frame:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                started = time.perf_counter()
                result = predictor.predict(rgb, explainability=explainability_config if explain_enabled else None)
                elapsed_ms = (time.perf_counter() - started) * 1000.0

                probs = result.get("probs", [0.0, 0.0, 0.0, 0.0])
                record = {
                    "frame_index": frame_index,
                    "timestamp_sec": round(frame_index / fps, 3) if fps > 0 else None,
                    "phase": result.get("phase", "unknown"),
                    "phase_id": _phase_index(result.get("phase", "unknown")),
                    "confidence": float(result.get("confidence", 0.0)),
                    "frames_used": int(result.get("frames_used", processed + 1)),
                    "idle": float(probs[0]) if len(probs) > 0 else 0.0,
                    "marking": float(probs[1]) if len(probs) > 1 else 0.0,
                    "injection": float(probs[2]) if len(probs) > 2 else 0.0,
                    "dissection": float(probs[3]) if len(probs) > 3 else 0.0,
                    "inference_ms": round(elapsed_ms, 3),
                }
                records.append(record)
                latest_overlay_result = {
                    "phase": record["phase"],
                    "confidence": record["confidence"],
                }
                processed += 1

                if explain_enabled and explainability_callback is not None:
                    explainability_callback(result.get("explainability"), processed, frame_index)

            if overlay_writer is None:
                overlay_writer, overlay_intermediate_path = create_overlay_video_writer(
                    frame_size=(frame.shape[1], frame.shape[0]),
                    fps=output_fps,
                    temp_dir=temp_path.parent,
                )

            overlay_frame = draw_prediction_overlay(
                frame,
                phase=latest_overlay_result["phase"],
                confidence=float(latest_overlay_result["confidence"]),
                model_label=model_label,
                frame_index=frame_index,
                fps=output_fps,
                total_frames=total_frames,
                sampled_frame=sampled_frame,
            )
            overlay_writer.write(overlay_frame)
            rendered_frames += 1

            if total_frames > 0:
                progress.progress(min(frame_index + 1, total_frames) / total_frames)
            else:
                progress.progress(min(processed / max_frames, 1.0))
            status.caption(
                f"Processed {processed} sampled frames · rendered {rendered_frames} playback frames"
            )

            frame_index += 1
            if sampled_frame and processed >= max_frames:
                truncated = total_frames <= 0 or frame_index < total_frames
                break
    except Exception:
        analysis_failed = True
        raise
    finally:
        capture.release()
        predictor.reset_state()
        if overlay_writer is not None:
            overlay_writer.release()
        progress.empty()
        status.empty()
        if analysis_failed and overlay_intermediate_path is not None:
            overlay_intermediate_path.unlink(missing_ok=True)

    annotated_video_path = None
    if overlay_intermediate_path is not None and rendered_frames > 0:
        transcoded_path, overlay_warning = transcode_video_for_streamlit(
            overlay_intermediate_path,
            temp_dir=temp_path.parent,
        )
        annotated_video_path = str(transcoded_path)

    analysis_meta = {
        "fps": fps,
        "total_frames": total_frames,
        "sampled_frames": processed,
        "rendered_frames": rendered_frames,
        "annotated_video_path": annotated_video_path,
        "annotated_video_warning": overlay_warning,
        "analysis_complete": not truncated,
    }
    if annotated_video_path is not None:
        annotated_path = Path(annotated_video_path)
        if annotated_path.exists():
            analysis_meta["annotated_video_size_label"] = format_bytes(annotated_path.stat().st_size)
            analysis_meta["annotated_video_duration_sec"] = rendered_frames / output_fps if output_fps > 0 else None

    return records, analysis_meta


def _render_single_result(result: dict):
    probs = result.get("probs", [0.0, 0.0, 0.0, 0.0])
    metrics = st.columns(3)
    metrics[0].metric("Predicted phase", result.get("phase", "unknown").upper())
    metrics[1].metric("Confidence", f"{float(result.get('confidence', 0.0)):.1%}")
    metrics[2].metric("Frames used", int(result.get("frames_used", 1)))

    prob_df = pd.DataFrame({"phase": list(PHASE_LABELS), "probability": probs})
    st.bar_chart(prob_df.set_index("phase"))
    st.download_button(
        label="Download JSON",
        data=json.dumps(result, indent=2, default=str).encode("utf-8"),
        file_name="phase_prediction.json",
        mime="application/json",
        key="download-single-json",
    )


def _render_video_results(records, meta):
    if not records:
        st.warning("No frames were processed from the uploaded video.")
        return

    annotated_video_path = meta.get("annotated_video_path")
    if annotated_video_path:
        st.subheader("Annotated playback")
        st.caption(
            "The analysed clip now includes a HUD-style phase overlay directly on the video frames, mirroring the live webapp feel."
        )
        st.video(annotated_video_path)
        overlay_details = []
        if meta.get("annotated_video_size_label"):
            overlay_details.append(f"overlay size {meta['annotated_video_size_label']}")
        if meta.get("rendered_frames"):
            overlay_details.append(f"{int(meta['rendered_frames'])} rendered frames")
        if overlay_details:
            st.caption(" · ".join(overlay_details))
    if meta.get("annotated_video_warning"):
        st.warning(meta["annotated_video_warning"])
    if not meta.get("analysis_complete", True):
        st.info(
            "The playback clip and tables cover only the analysed portion of the video because the sampled-frame limit was reached."
        )

    df = _records_to_frame(records)
    counts = Counter(df["phase"].tolist())
    dominant_phase, _ = counts.most_common(1)[0]

    metrics = st.columns(4)
    metrics[0].metric("Sampled frames", int(meta["sampled_frames"]))
    metrics[1].metric("Dominant phase", dominant_phase.upper())
    metrics[2].metric("Mean confidence", f"{df['confidence'].mean():.1%}")
    metrics[3].metric("Average inference", f"{df['inference_ms'].mean():.1f} ms")

    detail_cols = st.columns(5)
    detail_cols[0].metric("File size", meta.get("file_size_label", "Unknown"))
    detail_cols[1].metric("Duration", meta.get("duration_label", "Unknown"))
    detail_cols[2].metric("FPS", f"{meta.get('fps', 0.0):.2f}" if meta.get("fps") else "Unknown")
    detail_cols[3].metric("Frames", int(meta.get("total_frames", meta.get("frame_count", 0))))
    detail_cols[4].metric("Resolution", meta.get("resolution_label", "Unknown"))

    chart_df = df.copy()
    if "timestamp_sec" in chart_df and chart_df["timestamp_sec"].notna().any():
        chart_df = chart_df.set_index("timestamp_sec")
    else:
        chart_df = chart_df.set_index("frame_index")

    st.subheader("Confidence timeline")
    st.line_chart(chart_df[["confidence"]])

    st.subheader("Phase timeline")
    st.line_chart(chart_df[["phase_id"]])

    st.subheader("Per-frame predictions")
    st.dataframe(df, use_container_width=True, hide_index=True)

    json_payload, csv_payload = _download_payloads(df)
    left, right = st.columns(2)
    left.download_button("Download JSON", json_payload, file_name="phase_timeline.json", mime="application/json")
    right.download_button("Download CSV", csv_payload, file_name="phase_timeline.csv", mime="text/csv")


def _render_workspace_page(
    enabled_model_keys: list[str], default_model_key: str, manager: SpaceModelManager
) -> None:
    availability_map = _model_availability_map(enabled_model_keys)
    _render_model_availability_sidebar(enabled_model_keys, availability_map)
    available_model_keys = [model_key for model_key in enabled_model_keys if availability_map[model_key].is_available]
    if not available_model_keys:
        st.error("None of the configured models are currently loadable in this Space.")
        _render_unavailable_model_notice(enabled_model_keys, availability_map)
        return

    resolved_default_model_key = default_model_key if default_model_key in available_model_keys else available_model_keys[0]
    previous_selected_model_key, model_key = _resolve_model_selection(available_model_keys, resolved_default_model_key)

    _render_workspace_header(enabled_model_keys, model_key)
    st.caption(_space_caption(enabled_model_keys))
    _render_unavailable_model_notice(enabled_model_keys, availability_map)

    st.session_state[SELECTED_MODEL_STATE_KEY] = model_key
    if previous_selected_model_key is not None and previous_selected_model_key != model_key:
        manager.unload_model()
        _clear_video_analysis()

    explainability_config, explainability_spec = _build_explainability_config(manager, model_key)

    source_summary = get_model_source_summary(model_key)
    st.sidebar.markdown("### Runtime")
    st.sidebar.write(f"Selected model: `{MODEL_LABELS[model_key]}`")
    st.sidebar.caption(MODEL_LOAD_NOTES[model_key])
    st.sidebar.write(f"CUDA available: `{torch.cuda.is_available()}`")
    if torch.cuda.is_available():
        st.sidebar.write(f"Device: `{torch.cuda.get_device_name(torch.cuda.current_device())}`")
        try:
            free_bytes, total_bytes = torch.cuda.mem_get_info()
            st.sidebar.write(
                f"GPU memory free: `{format_bytes(free_bytes)}` / `{format_bytes(total_bytes)}`"
            )
        except RuntimeError:
            pass
    st.sidebar.write(f"Model dir: `{source_summary['model_dir']}`")
    st.sidebar.write(f"HF repo: `{source_summary['repo_id'] or 'local-only'}`")
    if source_summary["subfolder"]:
        st.sidebar.write(f"Repo subfolder: `{source_summary['subfolder']}`")
    with st.sidebar.expander("Checkpoint requirements", expanded=False):
        st.write(", ".join(source_summary["required_files"]))
        if source_summary["optional_files"]:
            st.caption("Optional: " + ", ".join(source_summary["optional_files"]))
    st.sidebar.write(f"Video upload cap: `{STREAMLIT_SERVER_MAX_UPLOAD_MB} MB`")
    st.sidebar.write(f"Working storage free: `{format_bytes(get_workspace_free_bytes())}`")

    prepare_col, unload_col = st.sidebar.columns(2)
    if prepare_col.button("Load model", use_container_width=True):
        try:
            with st.spinner(f"Preparing {MODEL_LABELS[model_key]}..."):
                manager.get_predictor(model_key)
        except Exception as exc:
            st.sidebar.error(str(exc))
        else:
            st.sidebar.success(f"{MODEL_LABELS[model_key]} is ready.")
    if unload_col.button("Unload", use_container_width=True):
        manager.unload_model()
        st.sidebar.success("Model unloaded")

    manager_status = manager.status()
    if manager_status.is_loaded and manager_status.active_model_label:
        st.sidebar.success(f"Loaded model: {manager_status.active_model_label}")
    else:
        st.sidebar.info("No model is currently loaded.")
    if manager_status.last_error:
        st.sidebar.error(manager_status.last_error)

    image_tab, video_tab = st.tabs(["Image", "Video"])

    with image_tab:
        image_main_col, image_explain_col = st.columns([3, 2], gap="large")
        image_explain_placeholder = image_explain_col.empty()
        image_result = None

        with image_main_col:
            uploaded_image = st.file_uploader("Upload an RGB frame", type=["png", "jpg", "jpeg"], key="image-uploader")
            if uploaded_image is not None:
                rgb = _image_to_rgb(uploaded_image)
                st.image(rgb, caption=uploaded_image.name, use_container_width=True)
                if st.button("Run image inference", key="run-image"):
                    try:
                        with st.spinner(f"Running {MODEL_LABELS[model_key]} on {uploaded_image.name}..."):
                            predictor = manager.get_predictor(model_key)
                        predictor.reset_state()
                        started = time.perf_counter()
                        image_result = predictor.predict(
                            rgb,
                            explainability=explainability_config if explainability_config.get("enabled") else None,
                        )
                        image_result["inference_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
                        predictor.reset_state()
                    except Exception as exc:
                        st.error(str(exc))
                    else:
                        _render_single_result(image_result)

        _render_explainability_panel(
            image_explain_placeholder,
            image_result.get("explainability") if image_result else None,
            enabled=bool(explainability_config.get("enabled")),
            spec=explainability_spec,
            title="Explainability",
        )

    with video_tab:
        video_main_col, video_explain_col = st.columns([3, 2], gap="large")
        video_explain_placeholder = video_explain_col.empty()
        _render_explainability_panel(
            video_explain_placeholder,
            None,
            enabled=bool(explainability_config.get("enabled")),
            spec=explainability_spec,
            title="Explainability",
        )

        with video_main_col:
            frame_stride = st.slider("Analyze every Nth frame", min_value=1, max_value=30, value=5, step=1)
            max_frames = st.slider("Maximum sampled frames", min_value=10, max_value=600, value=180, step=10)
            uploaded_video = st.file_uploader(
                "Upload a video (MP4 preferred)",
                type=SUPPORTED_VIDEO_TYPES,
                key="video-uploader",
                help=(
                    f"Single-file uploads are enabled up to {STREAMLIT_SERVER_MAX_UPLOAD_MB} MB. "
                    "MP4 is preferred; MOV/AVI/MKV/WEBM/M4V stay enabled as fallback containers."
                ),
                max_upload_size=STREAMLIT_SERVER_MAX_UPLOAD_MB,
            )
            if uploaded_video is not None:
                try:
                    temp_path, video_meta = _prepare_staged_video(uploaded_video)
                except Exception as exc:
                    st.error(str(exc))
                else:
                    analysis_signature = _video_analysis_signature(
                        st.session_state.get("staged_video_signature"),
                        model_key,
                        frame_stride,
                        max_frames,
                    )
                    saved_analysis = st.session_state.get(VIDEO_ANALYSIS_STATE_KEY)
                    if saved_analysis and saved_analysis.get("signature") != analysis_signature:
                        _clear_video_analysis()
                        saved_analysis = None

                    info_cols = st.columns(5)
                    info_cols[0].metric("File size", video_meta["file_size_label"])
                    info_cols[1].metric("Duration", video_meta["duration_label"])
                    info_cols[2].metric("FPS", f"{video_meta.get('fps', 0.0):.2f}" if video_meta.get("fps") else "Unknown")
                    info_cols[3].metric("Frames", int(video_meta.get("frame_count", 0)))
                    info_cols[4].metric("Resolution", video_meta["resolution_label"])
                    if video_meta.get("format_name"):
                        st.caption(f"Container detected by ffprobe: {video_meta['format_name']}")

                    recommended_stride = recommended_frame_stride(video_meta.get("duration_seconds"))
                    st.caption(
                        f"Recommended frame stride for this video: every {recommended_stride} frame(s). "
                        "Use higher values for very long videos to keep analysis times reasonable."
                    )

                    if should_show_inline_preview(video_meta["file_size_bytes"]):
                        st.video(uploaded_video)
                    else:
                        st.info(
                            "Inline preview is disabled for uploads larger than "
                            "256 MB to avoid pushing very large media back through the browser. "
                            "The staged video on disk is still used for analysis."
                        )

                    if st.button("Analyze video", key="run-video"):
                        latest_payload = {"value": None}

                        def _video_explainability_callback(payload, processed_count: int, current_frame_index: int):
                            latest_payload["value"] = payload
                            _render_explainability_panel(
                                video_explain_placeholder,
                                payload,
                                enabled=True,
                                spec=explainability_spec,
                                title=f"Live explainability · sampled frame {processed_count}",
                            )

                        _clear_video_analysis()
                        try:
                            with st.spinner(f"Running {MODEL_LABELS[model_key]} on {uploaded_video.name}..."):
                                predictor = manager.get_predictor(model_key)
                            records, analysis_meta = _analyse_video(
                                temp_path,
                                predictor,
                                frame_stride=frame_stride,
                                max_frames=max_frames,
                                video_info=video_meta,
                                model_label=MODEL_LABELS[model_key],
                                explainability_config=explainability_config if explainability_config.get("enabled") else None,
                                explainability_callback=(
                                    _video_explainability_callback
                                    if explainability_config.get("enabled")
                                    else None
                                ),
                            )
                            meta = {
                                **video_meta,
                                **analysis_meta,
                            }
                            st.session_state[VIDEO_ANALYSIS_STATE_KEY] = {
                                "signature": analysis_signature,
                                "records": records,
                                "meta": meta,
                                "annotated_video_path": meta.get("annotated_video_path"),
                                "latest_explainability": latest_payload["value"],
                            }
                            saved_analysis = st.session_state[VIDEO_ANALYSIS_STATE_KEY]
                        except Exception as exc:
                            st.error(str(exc))

                    saved_analysis = st.session_state.get(VIDEO_ANALYSIS_STATE_KEY)
                    if saved_analysis and saved_analysis.get("signature") == analysis_signature:
                        _render_video_results(saved_analysis["records"], saved_analysis["meta"])
                        if explainability_config.get("enabled"):
                            _render_explainability_panel(
                                video_explain_placeholder,
                                saved_analysis.get("latest_explainability"),
                                enabled=True,
                                spec=explainability_spec,
                                title="Explainability",
                            )
            else:
                _clear_video_stage()


def main():
    enabled_model_keys = _enabled_model_keys()
    default_model_key = _default_model_key(enabled_model_keys)
    manager = _get_model_manager()
    _inject_app_styles()
    
    # Get current page but only render nav if not on intro
    current_page = _current_portfolio_page()
    
    if current_page == "intro":
        if _render_intro_page:
            _render_intro_page()
        else:
            st.error("Intro page not available. Please check dependencies.")
        return

    # Render navigation for all other pages
    _render_page_navigation()

    if current_page == "home":
        _render_project_hub(enabled_model_keys)
        return

    if current_page == "projects":
        _render_projects_page()
        return

    if current_page == "technical":
        _render_technical_page()
        return

    if current_page == "relp_sae":
        if _render_relp_sae_page:
            _render_relp_sae_page()
        else:
            st.error("RelP-SAE page not available. Please check dependencies.")
        return

    if current_page == "gemma_grook":
        if _render_gemma_grook_page:
            _render_gemma_grook_page()
        else:
            st.error("Gemma-GR00T page not available. Please check dependencies.")
        return

    if current_page == "parameter_golf":
        if _render_parameter_golf_page:
            _render_parameter_golf_page()
        else:
            st.error("Parameter Golf page not available. Please check dependencies.")
        return

    if current_page == "cosmos_sentinel":
        _render_cosmos_sentinel_page()
        return

    if current_page == "syndrome_net":
        _render_syndrome_net_page()
        return

    if current_page == "enterprise_dashboard":
        _render_enterprise_dashboard()
        return

    _render_workspace_page(enabled_model_keys, default_model_key, manager)


if __name__ == "__main__":
    main()
