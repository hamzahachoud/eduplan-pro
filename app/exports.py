import csv
import io
from flask import Response
from fpdf import FPDF
from datetime import datetime

class PDFPlanning(FPDF):
    def __init__(self, title_text, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title_text = title_text

    def header(self):
        # Arial bold 15
        self.set_font('Arial', 'B', 15)
        # Move to the right
        self.cell(80)
        # Title
        self.cell(120, 10, self.title_text, border=0, align='C')
        # Line break
        self.ln(15)

    def footer(self):
        # Position at 1.5 cm from bottom
        self.set_y(-15)
        # Arial italic 8
        self.set_font('Arial', 'I', 8)
        # Page number
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}} - Généré le {datetime.now().strftime("%d/%m/%Y %H:%M")}', 0, 0, 'C')

def generate_csv_response(filename, header, rows):
    """
    Génère une réponse HTTP contenant un fichier CSV (avec BOM pour Excel).
    """
    si = io.StringIO()
    # Ajout du BOM UTF-8 pour forcer Excel à lire les accents correctement
    si.write('\ufeff')
    writer = csv.writer(si, delimiter=';', lineterminator='\r\n')
    writer.writerow(header)
    writer.writerows(rows)
    
    output = si.getvalue()
    si.close()
    
    return Response(
        output,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

def generate_pdf_response(filename, title, seances):
    """
    Génère un fichier PDF tabulaire listant des séances de manière propre.
    """
    pdf = PDFPlanning(title_text=title, orientation='L', format='A4') # Paysage pour avoir de la place
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 10)

    # Couleurs d'en-tête (Bleu foncé)
    pdf.set_fill_color(15, 23, 42)
    pdf.set_text_color(255, 255, 255)

    # Largeurs des colonnes (Total = 277 en A4 Paysage avec marges par défaut de 10)
    col_widths = [25, 20, 20, 50, 20, 25, 60, 40]
    headers = ["Date", "Début", "Fin", "Module", "Type", "Groupe", "Enseignant", "Salle"]

    for i in range(len(headers)):
        pdf.cell(col_widths[i], 8, headers[i], border=1, fill=True, align='C')
    pdf.ln()

    # Rétablissement des couleurs pour le corps
    pdf.set_fill_color(245, 245, 245)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('Arial', '', 9)

    fill = False
    for s in seances:
        date_str = s.date_seance.strftime('%d/%m/%Y')
        heure_deb = s.heure_debut.strftime('%H:%M')
        heure_fin = s.heure_fin.strftime('%H:%M')
        module = (s.module.code[:20] + '..') if len(s.module.code) > 20 else s.module.code
        type_s = s.type_seance
        groupe = s.groupe
        prof = s.enseignant.nom_complet() if s.enseignant else 'N/A'
        prof = (prof[:30] + '..') if len(prof) > 30 else prof
        salle = s.salle.nom if s.salle else 'N/A'

        pdf.cell(col_widths[0], 7, date_str, border=1, fill=fill, align='C')
        pdf.cell(col_widths[1], 7, heure_deb, border=1, fill=fill, align='C')
        pdf.cell(col_widths[2], 7, heure_fin, border=1, fill=fill, align='C')
        pdf.cell(col_widths[3], 7, module, border=1, fill=fill)
        pdf.cell(col_widths[4], 7, type_s, border=1, fill=fill, align='C')
        pdf.cell(col_widths[5], 7, groupe, border=1, fill=fill, align='C')
        pdf.cell(col_widths[6], 7, prof, border=1, fill=fill)
        pdf.cell(col_widths[7], 7, salle, border=1, fill=fill, align='C')
        pdf.ln()
        
        fill = not fill # Alternance de couleurs des lignes

    pdf_output = bytes(pdf.output())

    return Response(
        pdf_output,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
