#import "../_template/logbook.typ": pbl_logbook
#let data = json("data.json")

#show: pbl_logbook.with(
  week_number: data.week_number,
  period: data.period,
  sprint_name: data.sprint_name,
  checkpoint_target: data.checkpoint_target,
  activities: data.activities,
  evaluations: data.evaluations,
)

#data.summary
