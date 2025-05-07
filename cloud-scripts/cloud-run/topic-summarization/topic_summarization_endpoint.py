# Google Cloud Function Impl
#   [Purpose]
#       Summarizes list of given pubmed abstracts from PubTrends TOPIC cluster. Function
#       is called with filtered list of abstracts, current implementation selects up to
#       top 50 abstracts with the greatest connectivity. This implementation
#       is based Gemini prompt which also tries to keep references to papers, used for
#       sentences in summary text

import functions_framework
import json
from flask import Request, jsonify
from google import genai
from google.genai import types
from enum import Enum
import os

# XXX: Configure through env variables!
VERTEX_CLIENT_PROJECT = os.environ.get('GCP_PROJECT') or 'my_project'


SYSTEM_INSTRUCTIONS_LLM_PROMPT_SUMMARIZE_ABSTRACT = """
You are a research bot, tasked with helping scientific researchers to explore scientific papers quicker. Your job is to summarize the text submitted to you.

Be sure to:
* do not add title to the summary
* NEVER make summary longer than 400 words
* tell as a story where each sentence are ALWAYS logically connected with previous
* put by NO MEANS short sentences that are not logically connected
* focus on the main points of the text
* keep it condense and to the point
* submitted text is set of blocks, each block marked with own ID, it is the line in the block starting from PMID= prefix
* if some sentence from summary is based on information from one or more blocks, specify at the end of this sentence block IDs used to generate the sentence
* Organize block IDs as coma-separated list in round brackets, e.g  (PMID=0000001, PMID=11111111, PMID=777777)
* do not hallucinate, please never hallucinate


<EXCEPTION>
do not put by NO MEANS short sentences like below:

**Comprehensive Analysis of Aging Mechanisms and Potential Interventions**

Aging leads to various cellular and molecular changes, contributing to age-related diseases and functional decline. Several studies explore these mechanisms and potential interventions.

One study found that Procyanidin C1 (PCC1), a compound with senolytic and senomorphic properties, counteracts aging-related changes in the hematopoietic and immune system by improving physiological parameters, increasing B cells and hematopoietic stem cells, suppressing senescence markers, and restoring immune homeostasis. PMID=40316527

Skeletal muscle deterioration, a hallmark of aging, involves reduced SIRT5 expression, leading to cellular senescence and inflammation; SIRT5 desuccinylates TBK1, suppressing inflammation and improving muscle function, suggesting the SIRT5-TBK1 pathway as a target for combating age-related muscle degeneration. PMID=40087407

Endothelial cell senescence, resulting from telomerase inactivation, induces transcriptional changes indicative of senescence and tissue hypoxia, compromising the blood-brain barrier and reducing muscle endurance, indicating that Tert loss causes EC senescence through a telomere length-independent mechanism undermining mitochondrial function. PMID=38475941

Blood-borne factors like osteocalcin (OCN) are crucial for maintaining neuronal synaptic plasticity, and OCN's effects are mediated by a primary cilium (PC) protein-autophagy axis; during aging, autophagy and PC core proteins are reduced, and restoring their levels improves cognitive impairments, suggesting the PC-autophagy axis as a gateway for communication between blood-borne factors and neurons. PMID=39984747

Mitochondrial dysfunction is a key aging determinant, and defects in mitochondrial protein and organelle quality control have been linked to various age-related diseases. PMID=37731280

Hyperactivation of mTORC1 signaling with aging contributes to cardiac dysfunction by dysregulating proteostasis, as shown in a 4EBP1 KO mouse model mimicking a hyperactive mTORC1/4EBP1/eIF4E axis. PMID=39379739

Dietary protein, particularly branched-chain amino acids (BCAAs), influences healthy aging; BCAA restriction protects against metabolic consequences of high protein diets and has tissue-specific effects on cellular senescence. PMID=39868338

Macroautophagy decreases with age, but mitophagy, the selective autophagic degradation of mitochondria, may increase or remain unchanged; pharmacological induction of mitophagy attenuates inflammation and ameliorates neurological function, pointing to mitophagy induction as a strategy to decrease age-associated inflammation. PMID=38280852

PGC-1, a mitochondrial regulator, is repressed with aging in the brain and is integral in coordinating metabolism and growth signaling, placing it centrally in a growth and metabolism network relevant to brain aging. PMID=40021651

Apigenin, a bioactive plant compound, may protect against age-related cognitive dysfunction by suppressing neuro-inflammatory processes driven by glial cells. PMID=38007051

Inhibition of mitochondrial malate dehydrogenase (MDH2) delays the aging process through metabolic-epigenetic regulation, identifying MDH2 as a potential therapeutic target for anti-aging drug development. PMID=39962087

The SATB protein DVE-1 influences lifespan independent of its canonical mitoUPR function, suggesting broader functions in modulating longevity and defending against stress. PMID=39423131

TFEB deficiency in the proximal tubules causes metabolic disorders and mitochondrial dysfunction, shedding light on the mechanisms of APOA4 amyloidosis pathogenesis and providing a therapeutic strategy for CKD-related metabolic disorders. PMID=39699959

β-hydroxybutyrate (HB), a ketone body, regulates protein solubility, selectively targeting pathological proteins like amyloid-β, suggesting a metabolically regulated mechanism of proteostasis relevant to aging and Alzheimer's disease. PMID=39626664

LRP5 promotes lower-body fat distribution and enhances insulin sensitivity, independent of its bone-related functions, and its activation may prevent age-related fat redistribution and metabolic disorders. PMID=40000740

Aging promotes STAT1 β-hydroxybutyrylation, attenuating IFN-I-mediated antiviral defense activity, and fructose can improve IFN-I antiviral defense activity by orchestrating STAT1 O-GlcNAc and β-hydroxybutyrylation modifications. PMID=39979583

HIRA and PML are essential for SASP expression, activating SASP through a CCF-cGAS-STING-TBK1-NF-κB pathway. PMID=39178863

TMEM242 depletion impairs ATP synthase, elevates ROS, upregulates sirt6 and nrf2, and increases f9a transcripts, potentially leading to bleeding tendencies. PMID=39856164

A disease-causing mutation of ABCA6 is identified for FPD, and ABCA6 is correlated with PD occurrence and subsequent OA progression, serving as a potential target in chondrogenesis and OA treatment by orchestrated intracellular cholesterol efflux and delayed cellular senescence. PMID=39823538

Endogenous DNA damage promotes hallmarks of age-related retinal degeneration, as shown in Ercc1-/- mice, which model a human progeroid syndrome. PMID=39604117

ACSS2 promotes the acetylation of PAICS, limiting purine metabolism and exacerbating cytoplasmic chromatin fragment accumulation and SASP, identifying ACSS2 as a potential senomorphic target to prevent senescence-associated diseases. PMID=40021646

SPP1 activates ITG5/1 to inhibit mitophagy, accelerates NPs degeneration, and induces calcification, leading to intervertebral disc degeneration (IVDD) and calcification. PMID=39721032

STXBP5 overexpression accelerates senescence, while STXBP5 deletion suppresses progerin expression, delaying senility, and decreasing the expression of senescence-related factors. PMID=39379476

Compartment-targeted FlucDM sensors pinpoint a diverse modulation of subcellular proteostasis by aging regulators. PMID=39383859

IGF-1 signaling plays a crucial role in preserving a youthful cerebromicrovascular endothelial phenotype and maintaining the integrity of the BBB. PMID=38082450

Aged hippocampal mitochondria exhibit impaired bioenergetic function, increased ROS production, deregulation of calcium homeostasis, and decreased mitochondrial biogenesis. PMID=36982549

TBK1-ATAD3A-Pink1 axis drives cellular senescence, suggesting a potential mitochondrial target for anti-aging therapy. PMID=39520088

Aging causes widespread reduction of proteins enriched in basic amino acids that is independent of mRNA regulation, and aberrant translation pausing leads to reduced ribosome availability resulting in proteome remodeling. PMID=38260253

Cysteine oxidation of muscle proteins impairs muscle power and strength, walking speed, and cardiopulmonary fitness with aging. PMID=38332629

CUL2FEM1B senses ROS produced by complex III of the electron transport chain (ETC), helping cells adjust their ETC to changing environments. PMID=39642856

HSF-1 mediates lifespan extension through mitochondrial network adaptations that occur in response to down-tuning of components associated with organellar protein degradation pathways. PMID=39532882

YBR238C oppositely affect mitochondria and aging, modulating mitochondrial function, demonstrating a feedback loop between TORC1 and mitochondria (the TORC1-MItochondria-TORC1 (TOMITO) signaling process) that regulates cellular aging processes. PMID=38713053

Mitochondrial metabolic modulation contributes to the longevity of daf-2 mutants, highlighting the crucial role of mitochondria in aging. PMID=40136535

MAVS safeguards mitochondrial homeostasis and antagonizes human stem cell senescence. PMID=37521327

TMEM135 is crucial for regulating mitochondria, peroxisomes, and lipids, emphasizing the importance of a balanced TMEM135 function for the health of the retina and other tissues. PMID=38576540

Blocking neddylation increased cellular hallmarks of aging and led to an increase in Tau aggregation and phosphorylation in neurons carrying the APPswe/swe mutation, indicating that cellular aging can reveal late-onset disease phenotypes. PMID=38917806

Mitochondrial DNA turnover in rat skeletal muscle decreases with age, contributing to losses of mitochondrial genomic integrity and potentially playing a role in skeletal muscle dysfunction. PMID=39312152

Suppression of NF-κB in cardiomyocytes leads to pronounced cardiac remodeling, dysfunction, and cellular damage associated with the aging process, influencing both cellular senescence and molecular damage pathways. PMID=39857807

MicroRNAs and neuropeptide-like proteins can form molecular regulatory networks involving downstream molecules to regulate lifespan, and such regulatory effects vary on environmental conditions. PMID=39323014

Pharmacological elevation of CISD2 expression at a late-life stage using hesperetin treatment is a feasible approach to effectively mitigating both intrinsic and extrinsic skin aging. PMID=38263133

Oxidative protein folding in the ER promotes cell aging, providing a potential target for aging and aging-related disease intervention. PMID=37306027

Mitochondrial morphology changes during aging, and C. elegans serve as a robust model for rapidly measuring mitochondrial

* Do not put same PMID in the one coma-separated list, like below:

Yin-Chen-Hao-Tang (YCHT) exhibited anti-fibrotic effects on the liver, potentially by suppressing oxidative stress and lipid peroxidation, restoring levels of metabolites like unsaturated fatty acids and lysophosphatidylcholines (PMID=26805802). Sophora flavescens (Kushen) itself showed anti-fibrosis activity, with studies identifying potential active compounds and targets through integrated network pharmacology and biomedical analysis (PMID=27754507). Fufang Biejia Ruangan Pill (FFBJ), an approved anti-fibrosis drug, contains various components including organic acids, terpenoids, flavonoids, phenylpropanoids, and alkaloids, with studies identifying absorbed components in vivo to understand its material basis (PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854, PMID=26724854,

</EXCEPTION>
"""

@functions_framework.http
def summarize_topic(request: Request):
    try:
        topic_data = request.get_json(silent=True)
        # topic_data_raw = topic_data
        if not topic_data:
            return jsonify({"error": "Missing or invalid JSON body"}), 400

        # If it's still a string (e.g. '{"a": 1, "b": 2}' as a str)
        if isinstance(topic_data, str):
            try:
                topic_data = json.loads(topic_data)
            except json.JSONDecodeError:
                return jsonify({"error": "Cannot parse JSON body"}), 400

        if 'abstracts' not in topic_data:
            return jsonify({
                "error": "Missing required key 'abstracts' in JSON body"
                # "error": f"Missing required key 'abstracts' in JSON body. Raw data type: {type(topic_data_raw)}, Parsed data type: {type(topic_data)}  Keys: {','.join(list(topic_data.keys()))}"
            }), 400
        abstract_entries = topic_data['abstracts']

        validated_entries = []
        for entry in abstract_entries:
            assert 'id' in entry
            assert 'abstract' in entry

            pmid = entry['id']
            abstract = entry['abstract']

            # TODO: validate id & abstract size & type, truncated if too long

            validated_entries.append(dict(pmid=pmid, abstract=abstract))

        assert len(abstract_entries) == len(validated_entries)

        output_text = do_llm_prompt_summarize_abstracts(validated_entries)

        return jsonify({
            'summary': output_text,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

def do_llm_prompt_summarize_abstracts(entries):
    args = dict(
        model="gemini-2.5-flash-preview-04-17", thinking_budget=1000,
        temperature=0.1, top_p=0.75, top_k=30, max_output_tokens=8192, #16384, #8192
    )

    text_to_summarize = "\n".join(f"\nPMID={e['pmid']}\n{e['abstract']}" for e in entries)

    llm_response = llm_generate(
        project=VERTEX_CLIENT_PROJECT,
        system_instructions=SYSTEM_INSTRUCTIONS_LLM_PROMPT_SUMMARIZE_ABSTRACT,
        text_to_summarize=text_to_summarize,
        **args
    )

    #print(llm_response)
    print("[DONE] Response len", len(llm_response))

    return llm_response

def llm_generate(
        *,
        project,
        system_instructions,
        text_to_summarize,
        model, temperature, top_p, top_k, max_output_tokens,
        thinking_budget=None,
        max_retries=5
):
    # print(text_to_summarize)
    # if True:
    #     return ""

    client = genai.Client(
        vertexai=True,
        project=project,
        location="us-central1",
    )

    msg1_text1 = types.Part.from_text(text=text_to_summarize)
    si_text1 = system_instructions

    contents = [types.Content(role="user", parts=[msg1_text1])]

    optional_args = {}
    if thinking_budget is not None:
        optional_args['thinking_config'] = types.ThinkingConfig(thinking_budget=thinking_budget)

    generate_content_config = types.GenerateContentConfig(
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
        seed=0,
        max_output_tokens=max_output_tokens,
        response_modalities=["TEXT"],
        safety_settings=[types.SafetySetting(
            category="HARM_CATEGORY_HATE_SPEECH",
            threshold="OFF"
        ), types.SafetySetting(
            category="HARM_CATEGORY_DANGEROUS_CONTENT",
            threshold="OFF"
        ), types.SafetySetting(
            category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
            threshold="OFF"
        ), types.SafetySetting(
            category="HARM_CATEGORY_HARASSMENT",
            threshold="OFF"
        )],
        system_instruction=[types.Part.from_text(text=si_text1)],
        **optional_args
    )

    retries_cnt = 0
    while retries_cnt < max_retries:
        chunks = []
        retries_cnt += 1

        for chunk in client.models.generate_content_stream(
                model=model,
                contents=contents,
                config=generate_content_config,
        ):
            assert chunk is not None
            if chunk.text is None:
                # when chunk.text is None - smth goes wrong - XXX: is know bug in 2.5 ==> REDO
                chunks = None
                break

            # if debug:
            #     print("CHUNK: [", chunk.text, end="]\n")

            if chunk.text is not None:
                chunks.append(chunk.text)

        # join chunks:
        if chunks is None:
            print(f"Retry #{retries_cnt}...")
            continue

        return "".join(chunks)

    raise Exception("Cannot summarize text. Maximum number of retries reached")
