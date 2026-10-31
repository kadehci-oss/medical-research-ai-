# Codex ortamı

Bu dosya ortamı oluşturmaz; Codex hesabında girilecek ayarları ve depodaki
kurulum betiğini tanımlar.

- Ortam adı: `medical-research-ai-`
- Depo: `kadehci-oss/medical-research-ai-`
- Başlangıç dalı: `main`
- Python: `3.12`
- Kurulum komutu: `bash .codex/setup.sh`
- Test komutu: `python -m pytest -q`
- Sözdizimi kontrolü: `python -m py_compile pubmed_client.py report_generator.py app.py`

Ortamı [Codex ortam ayarları](https://chatgpt.com/codex/settings/environments)
sayfasından oluşturun. Arayüzde önce ortamı test edip ardından kaydedin/yayımlayın.
Kurulum betiği, CI ile aynı `requirements.lock` dosyasını kurar ve bağımlılık
tutarlılığını denetler. Standart testlerde API anahtarı gerekmez.

Canlı PubMed/CrossRef araştırması çalıştırılacaksa ajan internet erişiminde
`eutils.ncbi.nlm.nih.gov` ve `api.crossref.org` alanlarına izin verin. Canlı
testler varsayılan olarak kapalıdır; `RUN_LIVE_PUBMED=1` ile ayrıca çalıştırılır.
İsteğe bağlı OpenAI sentezi için `OPENAI_API_KEY` çalışma ortamında ayrıca
tanımlanır; uygulamadaki veri aktarım onayı yine gereklidir. Anahtarları depoya
yazmayın.

Resmî belge: [Codex Cloud environments](https://learn.chatgpt.com/docs/environments/cloud-environments).
