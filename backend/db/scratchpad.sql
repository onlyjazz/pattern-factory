select subtype, company, n from 
(select substring(submission_number,1,1) as subtype, company, count(*) as n from products group by subtype, company)    
where subtype != 'K' OR (subtype = 'K' AND n = 1)
order by company, subtype;

Update the orgs and people tables to reflect the following:
Yann Gaston-Mathé is at Iktos
James Hamrick is at Precision Oncology Alliance at Caris Life Sciences
Aaron Brouser is at Natera
Tim O'Connell is at Emtelligent
Bar Rafaelli is at Carolina Lemke Berlin
Martin Rapaport is at Rapaport Group

 org_id |       name        
--------+-------------------
        | Yann Gaston-Mathé
        | James Hamrick
        | Aaron Brouser
        | Tim O'Connell
     14 | Alice Smith
     15 | Enrique Diloné
     17 | Tigran Arzumanov
      3 | Aaron Brauser
        | Bar Rafaeli
        | Martin Rapaport