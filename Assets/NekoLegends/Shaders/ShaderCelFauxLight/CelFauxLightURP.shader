Shader "Neko Legends/Cel Shader/Cel Faux Light URP (Free)"
{
    Properties
    {
        _MainTex ("Main Texture", 2D) = "white" {}
        _Color   ("Main Color", Color) = (1,1,0.75,1)

        _LightAzimuth   ("Light Horizontal Angle", Range(0,360)) = 230
        _LightElevation ("Light Vertical Angle",   Range(-90,90)) = 65

        _ShadingFalloff ("Shading Falloff (step size)", Range(0,1)) = 0.33
        _Brightness     ("Light & Shadows", Range(0,1)) = 0.33
        _RimOutput      ("Rim Threshold", Range(0,1)) = 0.3
        _RimColor       ("Rim Color", Color) = (1,1,1,1)

        [NoScaleOffset]_NormalTex ("Normal Texture", 2D) = "bump" {}
        _NormalIntensity("Normal Intensity", Range(0,2)) = 1

        _UseEmission     ("Use Emission", Range(0,1)) = 0
        _EmissionTex     ("Emission Texture", 2D) = "black" {}
        _EmissionColor   ("Emission Color", Color) = (1,1,1,1)
        _EmissionIntensity("Emission Intensity", Range(0,5)) = 1
    }

    SubShader
    {
        Tags{
            "RenderPipeline"="UniversalRenderPipeline"
            "RenderType"="Opaque"
            "Queue"="Geometry"
        }
        LOD 100

        Pass
        {
            Name "ForwardLit"
            Tags{ "LightMode"="UniversalForward" }

            HLSLPROGRAM
            #pragma vertex   vert
            #pragma fragment frag

            #pragma multi_compile_instancing
        
            #pragma target 3.0
            #pragma only_renderers d3d11 gles3 glcore metal vulkan

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
          
            struct Attributes
            {
                float4 positionOS : POSITION;
                float3 normalOS   : NORMAL;
                float2 uv0        : TEXCOORD0;
                float2 uv1        : TEXCOORD1;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct Varyings
            {
                float4 positionHCS : SV_POSITION;
                float2 uv          : TEXCOORD0;
                float2 uvEmission  : TEXCOORD1;
                float3 normalWS    : TEXCOORD2;
                float3 viewDirWS   : TEXCOORD3;
                float2 uvBump      : TEXCOORD4;
                float  fogCoord    : TEXCOORD5;
                UNITY_VERTEX_OUTPUT_STEREO
            };

            TEXTURE2D(_MainTex);     SAMPLER(sampler_MainTex);
            TEXTURE2D(_EmissionTex); SAMPLER(sampler_EmissionTex);
            TEXTURE2D(_NormalTex);   SAMPLER(sampler_NormalTex);

            float4 _MainTex_ST, _EmissionTex_ST, _Color;
            float  _ShadingFalloff, _Brightness, _RimOutput;
            float4 _RimColor;
            float  _UseEmission, _EmissionIntensity;
            float4 _EmissionColor;
            float  _NormalIntensity;
            float  _LightAzimuth, _LightElevation;

            float Quantize(float nDotL, float stepSize)
            {
                stepSize = max(stepSize, 0.0001);
                float bands = floor(saturate(nDotL) / stepSize);
                return bands * stepSize;
            }

            Varyings vert(Attributes IN)
            {
                Varyings OUT;
                UNITY_SETUP_INSTANCE_ID(IN);
                UNITY_TRANSFER_INSTANCE_ID(IN, OUT);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(OUT);

                float3 posWS      = TransformObjectToWorld(IN.positionOS.xyz);
                OUT.positionHCS   = TransformWorldToHClip(posWS);
                OUT.normalWS      = TransformObjectToWorldNormal(IN.normalOS);
                OUT.viewDirWS     = GetWorldSpaceViewDir(posWS);

                OUT.uv        = TRANSFORM_TEX(IN.uv0, _MainTex);
                OUT.uvEmission= TRANSFORM_TEX(IN.uv0, _EmissionTex);
                OUT.uvBump    = IN.uv1;

                OUT.fogCoord  = ComputeFogFactor(OUT.positionHCS.z);
                return OUT;
            }

            half4 frag(Varyings IN) : SV_Target
            {
                UNITY_SETUP_INSTANCE_ID(IN);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(IN);

                half4 baseCol = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, IN.uv) * _Color;

                float3 nWS = normalize(IN.normalWS);
                float useNrm = step(0.001, _NormalIntensity);
                float3 nrmSample = SAMPLE_TEXTURE2D(_NormalTex, sampler_NormalTex, IN.uvBump).xyz * 2.0 - 1.0;
                nWS = normalize(lerp(nWS, normalize(nWS + (nrmSample * (_NormalIntensity - 1.0))), useNrm));

                float phi   = _LightElevation * PI/180.0;
                float theta = (360.0 - _LightAzimuth) * PI/180.0;
                float3 L = float3(sin(phi)*cos(theta), cos(phi), sin(phi)*sin(theta));

                float toonVal = Quantize(max(0.0, dot(nWS, normalize(L))), _ShadingFalloff);

                float3 viewDir = normalize(IN.viewDirWS);
                float rimDot = 1.0 - dot(viewDir, nWS);
                float rim = smoothstep(_RimOutput, _RimOutput + 0.1, rimDot); // Adjust 0.1 for softness
                half3 rimCol = rim * _RimColor.rgb;

                half3 col = baseCol.rgb * (toonVal + _Brightness) + rimCol;

                half useEmi = step(0.5, _UseEmission);
                half3 emiTex = SAMPLE_TEXTURE2D(_EmissionTex, sampler_EmissionTex, IN.uvEmission).rgb;
                col += emiTex * _EmissionColor.rgb * _EmissionIntensity * useEmi;

                half4 finalCol = half4(col, 1);
                finalCol.rgb = MixFog(finalCol.rgb, IN.fogCoord);
                return finalCol;
            }
            ENDHLSL
        }
    }

    CustomEditorForRenderPipeline "NekoLegends.CelFauxLightInspector" "UnityEngine.Rendering.Universal.UniversalRenderPipelineAsset"
}
