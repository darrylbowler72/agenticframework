import jenkins.model.Jenkins

def jobName = "spring-petclinic-build"
def job = Jenkins.instance.getItemByFullName(jobName)

if (job != null) {
    job.scheduleBuild(0, new hudson.model.Cause.UserIdCause())
    println "Build triggered for job: ${jobName}"
} else {
    println "Job not found: ${jobName}"
}
