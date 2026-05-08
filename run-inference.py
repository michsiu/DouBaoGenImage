#!/usr/bin/env python3
"""
GitHub Actions 推理脚本 - 单条推理
用于在 CI/CD 环境中运行 Qwen2.5-Sex 模型推理
"""

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
import argparse
import os
import sys
from datetime import datetime


def parse_args():
    parser = argparse.ArgumentParser(description='Qwen2.5-Sex Model Inference')
    parser.add_argument('--prompt', type=str, required=True, help='输入提示词')
    parser.add_argument('--temperature', type=float, default=0.3, help='温度参数')
    parser.add_argument('--top-p', type=float, default=0.9, help='Top-p 采样参数')
    parser.add_argument('--top-k', type=int, default=80, help='Top-k 采样参数')
    parser.add_argument('--max-tokens', type=int, default=512, help='最大生成令牌数')
    parser.add_argument('--system-message', type=str, default='', help='系统消息')
    parser.add_argument('--model-path', type=str, default=None, help='模型路径（可选）')
    parser.add_argument('--output', type=str, default='result.txt', help='输出文件')
    return parser.parse_args()


def load_model(model_path=None):
    """加载模型和分词器"""
    print("正在加载模型...")
    
    if model_path is None:
        model_name = "ystemsrx/Qwen2.5-Sex"
    else:
        model_name = model_path
    
    print(f"模型: {model_name}")
    
    # 加载分词器
    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        trust_remote_code=True,
        resume_download=True
    )
    
    # 加载模型（CPU版本）
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.float32,
        device_map="cpu",
        trust_remote_code=True,
        resume_download=True,
        low_cpu_mem_usage=True
    )
    
    model.eval()
    print("模型加载完成！")
    print(f"模型参数量: {sum(p.numel() for p in model.parameters()) / 1e9:.2f}B")
    
    return model, tokenizer


def generate_response(model, tokenizer, prompt, system_message, temperature, top_p, top_k, max_tokens):
    """生成模型响应"""
    
    # 构建对话
    messages = []
    if system_message:
        messages.append({"role": "system", "content": system_message})
    messages.append({"role": "user", "content": prompt})
    
    # 应用聊天模板
    try:
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
    except AttributeError:
        # 后备方案
        text = "\n".join([f"{msg['role'].capitalize()}: {msg['content']}" for msg in messages])
        text += "\nAssistant:"
    
    # 编码输入
    model_inputs = tokenizer([text], return_tensors="pt")
    
    # 生成响应
    print(f"正在生成响应...")
    print(f"参数: temperature={temperature}, top_p={top_p}, top_k={top_k}, max_tokens={max_tokens}")
    
    with torch.no_grad():
        generated_ids = model.generate(
            model_inputs.input_ids,
            max_new_tokens=max_tokens,
            top_p=top_p,
            top_k=top_k,
            temperature=temperature,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id
        )
    
    # 解码输出
    generated_ids = [
        output_ids[len(input_ids):] 
        for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
    ]
    response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
    
    return response.strip()


def save_result(output_file, prompt, response, **params):
    """保存推理结果"""
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("Qwen2.5-Sex 模型推理结果\n")
        f.write("=" * 60 + "\n\n")
        
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("参数设置:\n")
        f.write(f"  - temperature: {params.get('temperature', 'N/A')}\n")
        f.write(f"  - top_p: {params.get('top_p', 'N/A')}\n")
        f.write(f"  - top_k: {params.get('top_k', 'N/A')}\n")
        f.write(f"  - max_tokens: {params.get('max_tokens', 'N/A')}\n")
        
        if params.get('system_message'):
            f.write(f"  - system_message: {params['system_message']}\n")
        
        f.write("\n" + "-" * 60 + "\n\n")
        
        f.write(f"用户输入:\n{prompt}\n\n")
        
        f.write("-" * 60 + "\n\n")
        
        f.write(f"模型输出:\n{response}\n\n")
        
        f.write("=" * 60 + "\n")

    print(f"\n结果已保存至: {output_file}")


def main():
    args = parse_args()
    
    # 显示配置信息
    print("\n" + "=" * 60)
    print("Qwen2.5-Sex 模型推理")
    print("=" * 60)
    print(f"提示词: {args.prompt}")
    print(f"温度: {args.temperature}")
    print(f"Top-P: {args.top_p}")
    print(f"Top-K: {args.top_k}")
    print(f"最大令牌数: {args.max_tokens}")
    if args.system_message:
        print(f"系统消息: {args.system_message}")
    print("-" * 60 + "\n")
    
    try:
        # 加载模型
        model, tokenizer = load_model(args.model_path)
        
        # 生成响应
        start_time = datetime.now()
        response = generate_response(
            model, tokenizer,
            prompt=args.prompt,
            system_message=args.system_message,
            temperature=args.temperature,
            top_p=args.top_p,
            top_k=args.top_k,
            max_tokens=args.max_tokens
        )
        elapsed = (datetime.now() - start_time).total_seconds()
        
        # 输出结果
        print("\n" + "=" * 60)
        print("生成完成!")
        print(f"耗时: {elapsed:.2f} 秒")
        print("=" * 60)
        print(response)
        print("=" * 60 + "\n")
        
        # 保存结果
        params = {
            'temperature': args.temperature,
            'top_p': args.top_p,
            'top_k': args.top_k,
            'max_tokens': args.max_tokens,
            'system_message': args.system_message
        }
        save_result(args.output, args.prompt, response, **params)
        
        # GitHub Actions 输出
        if 'GITHUB_OUTPUT' in os.environ:
            with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
                f.write(f"response<<EOF\n{response}\nEOF\n")
                f.write(f"elapsed_time={elapsed:.2f}\n")
        
        sys.exit(0)
        
    except Exception as e:
        print(f"\n错误: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()