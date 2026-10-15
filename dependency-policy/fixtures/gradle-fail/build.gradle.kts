tasks.register("check") {
    doLast {
        throw GradleException("controlled fixture failure")
    }
}
